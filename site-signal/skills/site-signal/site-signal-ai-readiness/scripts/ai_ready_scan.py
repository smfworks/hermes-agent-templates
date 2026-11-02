#!/usr/bin/env python3
"""AI-readiness scanner. Usage: python3 ai_ready_scan.py URL [--json out.json]

Port of SPEC.md Appendix A.2b (Grok Bot ai-ready/scan.py), verbatim in logic and
weights: critical 25 / serious 10 / moderate 5 / minor 2; A>=90 B>=75 C>=60
D>=40 F. Single change: fetches go through the shared polite fetcher
(lib/common/http.py — unified UA, robots.txt for our UA, 1 req/s, 20 s timeout),
per the Appendix A preamble allowance. Training bots are reported, not penalized.
The port also omits two provably dead no-ops present in A.2b itself (a bare
`for …: pass` loop); everything else is logic-identical.
"""
import sys, json, re, time, urllib.parse as up
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # profile root
from lib.common.http import polite_get, USER_AGENT as UA
from bs4 import BeautifulSoup
SEARCH_BOTS = ["OAI-SearchBot","ChatGPT-User","Claude-SearchBot","Claude-User","PerplexityBot","Perplexity-User","Googlebot","Bingbot"]
TRAIN_BOTS = ["GPTBot","ClaudeBot","Google-Extended","CCBot","Applebot-Extended","Meta-ExternalAgent"]
issues=[]; passes=[]
def add(impact,id,msg,fix): issues.append(dict(impact=impact,id=id,message=msg,fix=fix))
def ok(id,msg): passes.append(dict(id=id,message=msg))
def get(u,**k):
    try: return polite_get(u,**k)
    except Exception as e: return None

def robots_groups(txt):
    groups=[];cur=None;last_ua=False
    for line in txt.splitlines():
        line=line.split('#')[0].strip()
        if ':' not in line: continue
        k,v=[x.strip() for x in line.split(':',1)];k=k.lower()
        if k=='user-agent':
            if not last_ua: cur={'ua':[],'dis':[],'allow':[]};groups.append(cur)
            cur['ua'].append(v.lower());last_ua=True
        else:
            last_ua=False
            if cur is None: continue
            if k=='disallow' and v: cur['dis'].append(v)
            if k=='allow' and v: cur['allow'].append(v)
    return groups
def blocked_root(groups,bot):
    g=[x for x in groups if bot.lower() in x['ua']] or [x for x in groups if '*' in x['ua']]
    return any('/' in x['dis'] and '/' not in x['allow'] for x in g)

def main(url):
    if not url.startswith('http'): url='https://'+url
    t=time.time(); r=get(url, robots_exempt=True); el=time.time()-t  # F4: score the page per A.2b even when robots blocks our UA
    if r is None or r.status_code>=400:
        add('critical','page-fetch',f'Page did not load for a plain HTTP client ({getattr(r,"status_code","error")}).','Ensure the URL returns 200 to non-browser user agents; check WAF/bot-protection rules.'); return finish(url)
    base=f"{up.urlparse(r.url).scheme}://{up.urlparse(r.url).netloc}"
    ok('page-fetch',f'{r.status_code} in {el:.1f}s')
    if el>5: add('serious','response-time',f'HTML took {el:.1f}s.','AI fetchers time out quickly; aim for <2s TTFB (cache/CDN).')
    if 'cf-mitigated' in r.headers or 'challenge' in r.text[:3000].lower() and 'cloudflare' in r.text[:3000].lower():
        add('critical','bot-challenge','Response looks like a bot challenge page.','Allow verified AI search/user agents through the WAF.')
    xr=r.headers.get('X-Robots-Tag','')
    if re.search(r'noindex|noai|none',xr,re.I): add('serious','x-robots-tag',f'X-Robots-Tag: {xr}','Remove noindex/noai unless intended.')
    # robots
    rb=get(base+'/robots.txt', robots_exempt=True)  # F4: robots.txt itself is always fetched (3.3 rule 7)
    if rb is None or rb.status_code>=500: add('critical','robots-txt','robots.txt errors/unreachable — per RFC 9309 crawlers treat this as full disallow.','Serve a fast 200 robots.txt.'); groups=[]
    elif rb.status_code>=400 or 'user-agent' not in rb.text.lower(): add('moderate','robots-txt','No valid robots.txt.','Add /robots.txt with explicit AI bot rules and a Sitemap: line.'); groups=[]; rb=None
    else:
        groups=robots_groups(rb.text); ok('robots-txt','robots.txt present')
        sb=[b for b in SEARCH_BOTS if blocked_root(groups,b)]
        if sb: add('critical','robots-search-bots','AI search/user agents blocked: '+', '.join(sb),'Allow search & user-triggered agents (OAI-SearchBot, Claude-SearchBot, PerplexityBot, ChatGPT-User…) so you can be cited.')
        else: ok('robots-search-bots','AI search agents allowed')
        tb=[b for b in TRAIN_BOTS if blocked_root(groups,b)]
        named=[b for b in SEARCH_BOTS+TRAIN_BOTS if any(b.lower() in g['ua'] for g in groups)]
        if not named: add('minor','robots-ai-policy','robots.txt has no explicit AI-bot rules (relies on *).','Add named groups so your training vs search policy is explicit.')
        ok('robots-training-policy','Training bots blocked: '+(', '.join(tb) or 'none'))
    # sitemap
    sm=[l.split(':',1)[1].strip() for l in (rb.text.splitlines() if rb is not None else []) if l.lower().startswith('sitemap:')] or [base+'/sitemap.xml']
    s=get(sm[0])
    if s is None or s.status_code!=200 or '<' not in s.text[:200]: add('serious','sitemap','No reachable XML sitemap.','Publish /sitemap.xml and reference it in robots.txt.')
    else:
        ok('sitemap',sm[0])
        if '<lastmod>' not in s.text: add('minor','sitemap-lastmod','Sitemap has no <lastmod> dates.','Add accurate lastmod for freshness signals.')
    # llms.txt
    l=get(base+'/llms.txt')
    if l is None or l.status_code!=200 or '<html' in l.text[:500].lower(): add('moderate','llms-txt','No /llms.txt.','Add a Markdown /llms.txt: H1 site name, > summary, ## sections of key links (llmstxt.org).')
    else:
        ok('llms-txt','llms.txt present')
        if not l.text.lstrip().startswith('#'): add('minor','llms-txt-format','llms.txt does not start with an H1.','Follow llmstxt.org format.')
        if get(base+'/llms-full.txt') is None or get(base+'/llms-full.txt').status_code!=200: add('minor','llms-full','No /llms-full.txt.','Optional: full-content Markdown dump for agents.')
    # html
    soup=BeautifulSoup(r.text,'html.parser')
    for t in soup(['script','style','noscript','template']):
        if t.name=='script' and t.get('type')=='application/ld+json': continue
    raw=BeautifulSoup(r.text,'html.parser')
    for t in raw(['script','style','noscript','template','svg']): t.decompose()
    words=len(raw.get_text(' ',strip=True).split())
    if words<80: add('critical','ssr-content',f'Only {words} words in raw HTML — content likely JS-rendered.','Server-render or pre-render main content; most AI crawlers do not execute JS.')
    elif words<250: add('moderate','ssr-content',f'Thin raw-HTML text ({words} words).','Ensure key copy is in server HTML.')
    else: ok('ssr-content',f'{words} words in server HTML')
    mr=soup.find('meta',attrs={'name':re.compile('^robots$',re.I)})
    if mr and re.search(r'noindex|none',mr.get('content',''),re.I): add('critical','meta-robots','meta robots noindex.','Remove noindex on public pages.')
    title=soup.title.string.strip() if soup.title and soup.title.string else ''
    if not title: add('serious','title','Missing <title>.','Add a descriptive title.')
    else: ok('title',title)
    d=soup.find('meta',attrs={'name':'description'})
    if not d or not d.get('content','').strip(): add('serious','meta-description','Missing meta description.','Add a 120–160 char summary; AI snippets reuse it.')
    if not soup.find('link',rel='canonical'): add('moderate','canonical','No canonical link.','Add <link rel="canonical">.')
    if not (soup.html and soup.html.get('lang')): add('minor','html-lang','No <html lang>.','Declare language.')
    og=[p for p in ['og:title','og:description','og:image','og:type','og:url'] if not soup.find('meta',property=p)]
    if og: add('moderate','open-graph','Missing Open Graph: '+', '.join(og),'Add OG tags for link previews/agents.')
    if not soup.find('meta',attrs={'name':'twitter:card'}): add('minor','twitter-card','No twitter:card.','Add twitter:card summary_large_image.')
    ld=[]
    for s_ in soup.find_all('script',type='application/ld+json'):
        try:
            j=json.loads(s_.string or ''); ld+= j if isinstance(j,list) else j.get('@graph',[j])
        except Exception: add('serious','jsonld-invalid','A JSON-LD block fails to parse.','Fix JSON syntax (validate at validator.schema.org).')
    types=sorted({str(x.get('@type')) for x in ld if isinstance(x,dict)})
    if not ld: add('serious','structured-data','No JSON-LD structured data.','Add schema.org JSON-LD (Organization/WebSite on home; Article/Product/Book on detail pages).')
    else:
        ok('structured-data','JSON-LD types: '+', '.join(types))
        if not any(re.search('Organization|Person|WebSite',t) for t in types): add('minor','jsonld-entity','No Organization/Person/WebSite entity.','Add an entity node with name, url, logo, sameAs.')
    h1=soup.find_all('h1')
    if len(h1)!=1: add('moderate','single-h1',f'{len(h1)} <h1> elements.','Use exactly one descriptive h1.')
    lv=[int(h.name[1]) for h in soup.find_all(re.compile('^h[1-6]$'))]
    if any(b-a>1 for a,b in zip(lv,lv[1:])): add('minor','heading-order','Heading levels skip.','Keep a logical outline; agents chunk by headings.')
    if not soup.find('main'): add('moderate','landmark-main','No <main> landmark.','Wrap primary content in <main> so extractors find it.')
    imgs=soup.find_all('img'); na=[i for i in imgs if i.get('alt') is None]
    if na: add('moderate','img-alt',f'{len(na)}/{len(imgs)} images lack alt.','Add alt text; vision-less agents rely on it.')
    links=soup.find_all('a'); bad=[a for a in links if not a.get('href') or a['href'].startswith('javascript')]
    if bad: add('moderate','crawlable-links',f'{len(bad)} links without real href.','Use <a href> for navigation, not JS handlers.')
    if not (soup.find('meta',property='article:modified_time') or soup.find('time') or 'dateModified' in r.text): add('minor','freshness','No visible/structured modified date.','Expose dateModified in JSON-LD or <time>.')
    if not soup.find('link',rel='alternate',type=re.compile('rss|atom')): add('minor','feed','No RSS/Atom feed linked.','Link a feed for change discovery.')
    return finish(url)
ORDER={'critical':0,'serious':1,'moderate':2,'minor':3}
W={'critical':25,'serious':10,'moderate':5,'minor':2}
def finish(url):
    issues.sort(key=lambda i:ORDER[i['impact']])
    score=max(0,100-sum(W[i['impact']] for i in issues))
    return dict(url=url,score=score,grade='A' if score>=90 else 'B' if score>=75 else 'C' if score>=60 else 'D' if score>=40 else 'F',issues=issues,passes=passes)
if __name__=='__main__':
    rep=main(sys.argv[1])
    if '--json' in sys.argv: json.dump(rep,open(sys.argv[sys.argv.index('--json')+1],'w'),indent=2)
    print(f"AI-readiness: {rep['url']}  score {rep['score']}/100 ({rep['grade']})")
    for i in rep['issues']: print(f"[{i['impact'].upper()}] {i['id']}: {i['message']}\n    fix: {i['fix']}")
    print('PASSES: '+'; '.join(f"{p['id']}={p['message']}" for p in rep['passes']))

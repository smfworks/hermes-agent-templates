#!/usr/bin/env python3
"""SEO / GEO / AEO scanner. Usage: python3 seo_geo_aeo_scan.py URL [--json out.json] [--pages N]

Crawls home + key pages (about, blog index, content pages from sitemap) and scores
SEO, GEO, AEO 0-100.

Port of SPEC.md Appendix A.3b (Grok Bot seo-geo-aeo/scan.py), verbatim in logic and
weights: each category starts at 100, each distinct failed check counted once
site-wide, critical 25 / serious 12 / moderate 6 / minor 2; overall =
0.4*SEO + 0.3*GEO + 0.3*AEO; grades A>=90 B>=80 C>=70 D>=55 F. Single change:
fetches go through the shared polite fetcher (lib/common/http.py — unified UA,
robots.txt for our UA, 1 req/s, 20 s timeout), per the Appendix A preamble.
The port also omits one provably dead no-op present in A.3b itself (an
`if … and False: pass`); everything else is logic-identical.
"""
import sys, json, re, time, urllib.parse as up
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # profile root
from lib.common.http import polite_get, USER_AGENT as UA
from bs4 import BeautifulSoup
W={'critical':25,'serious':12,'moderate':6,'minor':2}
issues=[]
def add(cat,impact,id,msg,fix,page=None):
    issues.append(dict(category=cat,impact=impact,id=id,message=msg,fix=fix,page=page))
def get(u, robots_exempt=False):
    try: return polite_get(u, robots_exempt=robots_exempt)
    except Exception: return None
def jsonld(soup):
    out=[]
    for s in soup.find_all('script',type='application/ld+json'):
        try: d=json.loads(s.string or '')
        except Exception: continue
        st=[d]
        while st:
            x=st.pop()
            if isinstance(x,list): st+=x
            elif isinstance(x,dict):
                out.append(x); st+=[v for v in x.values() if isinstance(v,(dict,list))]
    return out
def types(objs):
    t=set()
    for o in objs:
        v=o.get('@type'); t.update(v if isinstance(v,list) else [v] if v else [])
    return t
QWORDS=r'^(what|why|how|when|who|which|where|is|are|can|does|do|should|will)\b'
def analyze(url,r,site):
    soup=BeautifulSoup(r.text,'html.parser'); P=up.urlparse(url).path or '/'
    head=soup.head or soup
    title=(soup.title.string or '').strip() if soup.title and soup.title.string else ''
    desc=(head.find('meta',attrs={'name':'description'}) or {}).get('content','').strip() if head.find('meta',attrs={'name':'description'}) else ''
    site['titles'].append((P,title)); site['descs'].append((P,desc))
    # SEO
    if not title: add('SEO','serious','title-missing','No <title>.','Add a unique 30-60 char title.',P)
    elif not 15<=len(title)<=65: add('SEO','minor','title-length',f'Title length {len(title)}: "{title[:80]}"','Aim for ~30-60 chars, primary topic first.',P)
    if not desc: add('SEO','serious','meta-description-missing','No meta description.','Add a unique 70-160 char description summarizing the page.',P)
    elif not 50<=len(desc)<=170: add('SEO','minor','meta-description-length',f'Description length {len(desc)}.','Aim for ~70-160 chars.',P)
    h1=soup.find_all('h1')
    if not h1: add('SEO','serious','h1-missing','No <h1>.','Add one descriptive H1.',P)
    elif len(h1)>1: add('SEO','minor','h1-multiple',f'{len(h1)} H1s.','Use a single H1 per page.',P)
    if not head.find('link',rel='canonical'): add('SEO','moderate','canonical-missing','No canonical link.','Add <link rel="canonical">.',P)
    rm=head.find('meta',attrs={'name':'robots'})
    if rm and 'noindex' in rm.get('content','').lower(): add('SEO','critical','noindex','Page is noindex.','Remove noindex if page should rank.',P)
    if not head.find('meta',attrs={'name':'viewport'}): add('SEO','serious','viewport','No viewport meta.','Add width=device-width viewport.',P)
    if not soup.html or not soup.html.get('lang'): add('SEO','minor','html-lang','No <html lang>.','Set lang attribute.',P)
    og={m.get('property') for m in head.find_all('meta',property=True)}
    miss=[k for k in ['og:title','og:description','og:image','og:url','og:type'] if k not in og]
    if miss: add('SEO','moderate' if 'og:image' in miss or 'og:title' in miss else 'minor','open-graph','Missing '+', '.join(miss),'Add complete Open Graph tags (and twitter:card).',P)
    if not head.find('meta',attrs={'name':'twitter:card'}): add('SEO','minor','twitter-card','No twitter:card.','Add twitter:card summary_large_image.',P)
    imgs=soup.find_all('img'); noalt=[i for i in imgs if i.get('alt') is None]
    if noalt: add('SEO','moderate','img-alt',f'{len(noalt)}/{len(imgs)} images lack alt.','Add descriptive alt (empty alt for decorative).',P)
    host=up.urlparse(url).netloc
    internal=[a for a in soup.find_all('a',href=True) if up.urlparse(up.urljoin(url,a['href'])).netloc==host]
    if len(internal)<5: add('SEO','moderate','internal-links',f'Only {len(internal)} internal links.','Link to related key pages.',P)
    body=BeautifulSoup(r.text,'html.parser')
    for t in body(['script','style','noscript','template','svg','nav','footer','header']): t.decompose()
    text=body.get_text(' ',strip=True); words=len(text.split())
    if words<250: add('SEO','moderate','thin-content',f'~{words} words of server-rendered main text.','Add substantive, server-rendered content.',P)
    if not url.startswith('https'): add('SEO','critical','https','Not HTTPS.','Serve over HTTPS.',P)
    # GEO
    ld=jsonld(soup); ty=types(ld)
    ARTICLE_TYPES={'Article','BlogPosting','NewsArticle','TechArticle','Book','LearningResource'}
    is_article=bool(re.search(r'/(blog|posts?|articles?|news|insights?|learn|books|guides|docs)/.+',P))
    if is_article:
        if not ty & ARTICLE_TYPES: add('GEO','serious','article-schema','Content page lacks Article/BlogPosting/Book/LearningResource JSON-LD.','Add BlogPosting with headline, author (Person), datePublished, dateModified, publisher.',P)
        else:
            a=[o for o in ld if types([o])&ARTICLE_TYPES][0]
            if not a.get('author'): add('GEO','serious','article-author','Article schema has no author.','Add author Person with name + url.',P)
            if not a.get('dateModified'): add('GEO','minor','date-modified','No dateModified.','Add dateModified for freshness.',P)
        if not (soup.find('time') or soup.find(attrs={'rel':'author'}) or re.search(r'\bby\s+[A-Z]',text[:1500])):
            add('GEO','moderate','visible-byline','No visible byline/date.','Show author name (linked to bio) and published/updated date.',P)
        stats=len(re.findall(r'\d+(\.\d+)?\s?(%|percent|x\b|million|billion)',text))
        if stats==0 and words>300: add('GEO','minor','facts-stats','No concrete numbers/statistics found.','Add specific facts, figures, and cited sources (GEO paper: +stats/citations raise visibility).',P)
        ext=[a for a in soup.find_all('a',href=True) if a['href'].startswith('http') and host not in a['href']]
        if not ext: add('GEO','minor','outbound-citations','No outbound source citations.','Cite authoritative sources inline.',P)
    if not ty & {'BreadcrumbList'} and P!='/': add('GEO','minor','breadcrumbs','No BreadcrumbList schema.','Add BreadcrumbList for entity/topic hierarchy.',P)
    site['types']|=ty; site['words']+=words
    # AEO
    hs=soup.find_all(['h2','h3']); q=[h for h in hs if h.get_text(strip=True).endswith('?') or re.match(QWORDS,h.get_text(strip=True),re.I)]
    site['qheads']+=len(q); site['lists']+=len(soup.find_all(['ol','ul','table','dl']))
    if q:
        short=0
        for h in q:
            n=h.find_next(['p','ul','ol'])
            if n and 20<=len(n.get_text(' ',strip=True).split())<=80: short+=1
        if short<len(q)/2: add('AEO','moderate','answer-paragraphs',f'{len(q)} question headings but few have a concise 40-60 word answer right after.','Put a direct 40-60 word answer immediately under each question heading.',P)
        if 'FAQPage' not in ty and len(q)>=3: add('AEO','minor','faq-schema','Q&A content without FAQPage schema.','Add FAQPage JSON-LD mirroring visible Q&A (helps Bing/answer engines; Google shows FAQ rich results only for gov/health).',P)
    if is_article:
        first=soup.find('article') or soup.find('main') or soup
        p=first.find('p')
        if not p or len(p.get_text(' ',strip=True).split())<20: add('AEO','moderate','lead-summary','No definition-style lead paragraph.','Open with a 1-2 sentence summary that directly answers the page’s core question.',P)
        if not q and len(hs)>=3: add('AEO','moderate','question-headings','No question-style subheadings.','Phrase some H2/H3s as the questions readers ask.',P)
    return soup
def main(url,maxp=5):
    if not url.startswith('http'): url='https://'+url
    site=dict(titles=[],descs=[],types=set(),words=0,qheads=0,lists=0)
    r=get(url)
    if r is None or r.status_code>=400: add('SEO','critical','fetch','Homepage failed.','Fix availability.'); return finish(url,[],site)
    base=f"{up.urlparse(r.url).scheme}://{up.urlparse(r.url).netloc}"
    soup=analyze(r.url,r,site); pages=[r.url]
    # candidate pages
    cand=[]
    for a in soup.find_all('a',href=True):
        u=up.urljoin(r.url,a['href']).split('#')[0]
        if u.startswith(base) and re.search(r'/(about|team|blog|faq)/?$',u): cand.append(u)
    sm=get(base+'/sitemap.xml'); locs=re.findall(r'<loc>(.*?)</loc>',sm.text) if sm is not None and sm.status_code==200 else []
    if not locs: add('SEO','serious','sitemap','No sitemap.xml.','Publish sitemap.')
    posts=[l for l in locs if re.search(r'/(blog|posts?|articles?|insights?|learn|books|guides|docs)/[^/]+/?$',l) and '/page/' not in l and '/series/' not in l]
    cand+=posts[:2]
    rb=get(base+'/robots.txt', robots_exempt=True)  # F4: robots.txt itself is always fetched (3.3 rule 7)
    if rb is None or rb.status_code!=200: add('SEO','moderate','robots','No robots.txt.','Add robots.txt with Sitemap line.')
    elif re.search(r'(?im)^user-agent:\s*\*\s*\n(?:.*\n)*?disallow:\s*/\s*$',rb.text): add('SEO','critical','robots-block','robots blocks /.','Allow crawling.')
    ll=get(base+'/llms.txt')
    if ll is None or ll.status_code!=200: add('GEO','minor','llms-txt','No /llms.txt.','Optional: add llms.txt (low evidence of impact).')
    for u in list(dict.fromkeys(cand))[:maxp-1]:
        if u.rstrip('/')==r.url.rstrip('/'): continue
        pr=get(u)
        if pr is None or pr.status_code>=400: add('SEO','serious','broken-key-page',f'{u} -> {getattr(pr,"status_code","err")}','Fix or remove link.',up.urlparse(u).path); continue
        analyze(pr.url,pr,site); pages.append(pr.url)
    # site-level
    for kind,lst in [('title',site['titles']),('description',site['descs'])]:
        c=Counter(v for _,v in lst if v); d=[v for v,n in c.items() if n>1]
        if d: add('SEO','moderate',f'duplicate-{kind}',f'Duplicate {kind} across pages: "{d[0][:70]}"',f'Make each page {kind} unique.')
    ty=site['types']
    if not ty & {'Organization','Person'}: add('GEO','serious','entity-schema','No Organization/Person entity schema.','Add Organization (name, url, logo, sameAs) and Person for authors.')
    else:
        org=[o for o in jsonld(soup) if types([o])&{'Organization','Person'}]
        if org and not any(o.get('sameAs') for o in org): add('GEO','moderate','sameas','Entity schema lacks sameAs profiles.','Add sameAs (GitHub, LinkedIn, X) to disambiguate the entity.')
    if 'WebSite' not in ty: add('GEO','minor','website-schema','No WebSite schema.','Add WebSite JSON-LD with name/url.')
    if not any(re.search(r'/(about|team)',p) for p in pages): add('GEO','serious','about-page','No reachable About/Team page linked from home.','Add an About page describing who you are, expertise, and contact (E-E-A-T).')
    if site['qheads']==0: add('AEO','serious','no-qa-content','No question-style headings anywhere sampled.','Add FAQ section(s) / question H2s with concise answers on key pages.')
    if 'FAQPage' not in ty and 'QAPage' not in ty: add('AEO','moderate','no-faq','No FAQ/QAPage content+schema sampled.','Add a visible FAQ on home/about with FAQPage JSON-LD.')
    if site['lists']<3: add('AEO','minor','structure','Little list/table structure.','Use lists/tables for steps & comparisons.')
    return finish(url,pages,site)
def finish(url,pages,site):
    scores={}
    for c in ['SEO','GEO','AEO']:
        seen={}
        for i in issues:
            if i['category']==c: seen.setdefault(i['id'],i)  # count each check once site-wide
        pen=sum(W[i['impact']] for i in seen.values()); scores[c]=max(0,100-pen)
    scores['overall']=round(0.4*scores['SEO']+0.3*scores['GEO']+0.3*scores['AEO'])
    g=lambda s:'A' if s>=90 else 'B' if s>=80 else 'C' if s>=70 else 'D' if s>=55 else 'F'
    order=list(W)
    iss=sorted(issues,key=lambda i:(order.index(i['impact']),i['category']))
    return dict(url=url,pages=pages,scores=scores,grades={k:g(v) for k,v in scores.items()},schema_types=sorted(t for t in site['types'] if t),issues=iss)
if __name__=='__main__':
    a=sys.argv[1:]; out=None; n=5
    if '--json' in a: out=a[a.index('--json')+1]
    if '--pages' in a: n=int(a[a.index('--pages')+1])
    rep=main(a[0],n)
    print(f"{rep['url']}  pages={len(rep['pages'])}")
    for k in ['SEO','GEO','AEO','overall']: print(f"  {k}: {rep['scores'][k]} ({rep['grades'][k]})")
    for i in rep['issues']: print(f"  [{i['impact']}] {i['category']} {i['id']} {i['page'] or ''}: {i['message']} -> {i['fix']}")
    if out: json.dump(rep,open(out,'w'),indent=2)

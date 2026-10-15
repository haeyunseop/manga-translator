import {test,expect} from '@playwright/test';

test('mocked quality rejection is clearly visible and preserves original text',async({page})=>{
 const job={id:'quality-test',title:'품질 확인 테스트',source:'upload',created:1,status:'done',stage:'처리 완료 · 확인 필요한 영역 있음',completed:1,total:1,error:null,pages:[{index:0,status:'ready',warnings:['1번 영역: 반복 출력을 감지해 원문을 유지했습니다.'],texts:[{text:'明日は図書館に行きます。',translation:'',confidence:90,review:true}]}]};
 await page.route('**/api/**',async route=>{
  const pathname=new URL(route.request().url()).pathname;
  if(pathname==='/api/jobs')return route.fulfill({json:[job]});
  if(pathname==='/api/health')return route.fulfill({json:{ocr:true,translation:true,font:true,engine:'mock for UI test',supported_hosts:[]}});
  if(pathname.includes('/pages/'))return route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aL1sAAAAASUVORK5CYII=','base64')});
  return route.fulfill({json:{authenticated:true}});
 });
 await page.goto('/');
 await page.getByRole('button',{name:/품질 확인 테스트/}).first().click();
 await expect(page.locator('.reader .page-label')).toContainText('처리 완료 · 확인 필요');
 await expect(page.locator('.reader [role="status"]')).toContainText('원문을 유지');
 await page.locator('.transcript summary').click();
 await expect(page.locator('.transcript')).toContainText('明日は図書館に行きます。');
 await expect(page.locator('.transcript')).toContainText('번역 검토 필요');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

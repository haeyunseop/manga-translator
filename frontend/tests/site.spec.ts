import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import {parse} from 'dotenv';
import {execFileSync} from 'node:child_process';
const password=parse(fs.readFileSync(path.resolve('../.env'))).MANGATRANS_PASSWORD;
if(!password)throw new Error('Generate a local .env with scripts/init_env.py first');

test.beforeAll(()=>{
 fs.mkdirSync('../artifacts',{recursive:true});
 const python=process.platform==='win32'?'../.venv/Scripts/python.exe':'../.venv/bin/python';
 execFileSync(python,['-c','import sys;sys.path.insert(0,"..");from backend.demo import make_demo;make_demo().save("../artifacts/browser-fixture.png")']);
});

test.beforeEach(async({page})=>{
 await page.goto('/');
 await page.getByLabel('서재 비밀번호').fill(password);
 await page.getByRole('button',{name:'서재 들어가기'}).click();
 await expect(page.getByRole('heading',{name:'새로운 이야기 시작하기'})).toBeVisible();
});

test('mobile login, real navigation and unsupported URL error',async({page})=>{
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await page.screenshot({path:'../artifacts/mobile-home.png',fullPage:true});
 await page.getByLabel('이미지 또는 작품 매니페스트 URL').fill('https://unsupported.example/manga');
 await page.getByLabel('제가 제작했거나 번역·처리할 권한이 있는 자료입니다.').check();
 await page.getByRole('button',{name:'번역하고 읽기'}).click();
 await expect(page.locator('.error[role="alert"]')).toContainText('지원하지 않는 사이트');
 await page.getByRole('tab',{name:'이미지 업로드'}).click();
 await expect(page.getByRole('button',{name:/번역할 페이지를 선택하세요/})).toBeVisible();
 await page.getByRole('button',{name:'서비스 안내'}).click();
 await expect(page.getByRole('dialog')).toBeVisible();
 await page.getByRole('button',{name:'확인했어요'}).click();
 await page.getByRole('button',{name:'로그아웃'}).click();
 await expect(page.getByLabel('서재 비밀번호')).toBeVisible();
});

test('demo completes with a real local model, or explicitly reports missing weights',async({page})=>{
 const health=await (await page.request.get('/api/health')).json();
 await page.getByRole('button',{name:'테스트 페이지 번역'}).click();
 await expect(page.locator('.reader h2')).toHaveText('작은 인사 · 자체 제작 테스트');
 if(!health.translation){
  await expect(page.locator('.error[role="alert"]')).toContainText('로컬 번역 모델이 없습니다');
  expect(await page.locator('.reader-page > img').count()).toBe(0);
 }else{
  await expect(page.locator('.reader-page > img')).toBeVisible({timeout:210_000});
  await expect.poll(()=>page.locator('.reader-page > img').evaluate(el=>(el as HTMLImageElement).complete&&(el as HTMLImageElement).naturalWidth>0)).toBe(true);
  await expect(page.locator('.page-label')).toContainText('번역 완료');
  await page.getByRole('button',{name:'원본',exact:true}).click();
  await expect(page.locator('.reader-page > img')).toHaveAttribute('src',/\/original$/);
  await page.getByRole('button',{name:'한국어',exact:true}).click();
  await expect(page.locator('.reader-page > img')).toHaveAttribute('src',/\/translated$/);
  await page.locator('.transcript summary').click();
  await expect(page.locator('.transcript')).toContainText('こんにちは');
  await page.screenshot({path:'../artifacts/mobile-translated.png',fullPage:true});
 }
 page.once('dialog',dialog=>dialog.accept());
 await page.getByRole('button',{name:'작은 인사 · 자체 제작 테스트 삭제'}).first().click();
});

test('real two-page upload, rendering and original switching',async({page})=>{
 const health=await (await page.request.get('/api/health')).json();
 test.skip(!health.translation,'Real local weights are absent; this is not a translation pass.');
 await page.getByRole('tab',{name:'이미지 업로드'}).click();
 const buffer=fs.readFileSync('../artifacts/browser-fixture.png');
 await page.locator('input[type="file"]').setInputFiles([{name:'01.png',mimeType:'image/png',buffer},{name:'02.png',mimeType:'image/png',buffer}]);
 await page.getByLabel('제가 제작했거나 번역·처리할 권한이 있는 자료입니다.').check();
 await page.getByLabel('원문 글 방향').selectOption('horizontal');
 const created=page.waitForResponse(r=>r.url().endsWith('/api/jobs/upload')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'번역하고 읽기'}).click();
 const response=await created;expect(response.status()).toBe(200);
 const {id}=await response.json();
 try{
  await expect(page.locator('.reader .page-label').filter({hasText:'번역 완료'})).toHaveCount(2,{timeout:210_000});
  const images=page.locator('.reader-page > img');
  await expect(images).toHaveCount(2);
  for(const image of await images.all())await expect.poll(()=>image.evaluate(el=>(el as HTMLImageElement).complete&&(el as HTMLImageElement).naturalWidth>0)).toBe(true);
  await page.getByRole('button',{name:'원본',exact:true}).click();
  for(const image of await images.all())await expect(image).toHaveAttribute('src',/\/original$/);
  await page.getByRole('button',{name:'한국어',exact:true}).click();
  for(const image of await images.all())await expect(image).toHaveAttribute('src',/\/translated$/);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'../artifacts/mobile-multiple.png',fullPage:true});
 }finally{
  const removed=await page.request.delete(`/api/jobs/${id}`);
  expect(removed.status()).toBe(200);
 }
});

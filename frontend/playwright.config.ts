import {defineConfig, devices} from '@playwright/test';
export default defineConfig({
 testDir:'./tests',timeout:240_000,workers:1,
 use:{baseURL:'http://127.0.0.1:3000',...devices['Pixel 7'],browserName:'chromium',launchOptions:{executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']},screenshot:'only-on-failure'},
 reporter:[['list']],outputDir:'../artifacts/browser-results'
});

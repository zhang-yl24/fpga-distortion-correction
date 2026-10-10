const fs=require('fs');
const {chromium}=require('C:/Users/22955/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base='C:/Users/22955/.codex/visualizations/2026/10/02/01a0fb52-2ab7-7c32-b506-ac557bf1b64b/';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const page=await browser.newPage({viewport:{width:768,height:1100},deviceScaleFactor:1.5});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const frag=fs.readFileSync(base+'pangu-wiring.html','utf8');
 await page.setContent('<html><head><style>:root{--background:#fff;--foreground:#18232b;--muted:#f0f3f4;--muted-foreground:#52616b;--border:#abb8c0;--viz-series-1:#147899}body{margin:16px;font-family:"Microsoft YaHei",sans-serif}</style></head><body>'+frag+'</body></html>');
 await page.locator('#pangu-wiring').screenshot({path:base+'pangu-wiring.png'});
 await page.setViewportSize({width:352,height:1200});
 await page.locator('#pangu-wiring').screenshot({path:base+'pangu-wiring-mobile.png'});
 console.log(JSON.stringify({errors,width:await page.locator('#pangu-wiring').evaluate(e=>e.clientWidth)}));
 await browser.close();
})();

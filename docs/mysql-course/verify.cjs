const { chromium } = require('playwright-core');
const { pathToFileURL } = require('node:url');
const path = require('node:path');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  const page = await browser.newPage();
  const errors = [], overflows = [];
  page.on('pageerror', err => errors.push(err.message));
  let checked = 0;
  for (const size of [{width:1366,height:768},{width:1920,height:1080},{width:390,height:844}]) {
    await page.setViewportSize(size);
    for (let lesson = 1; lesson <= 4; lesson++) {
      await page.goto(pathToFileURL(path.join(__dirname, `lesson-0${lesson}.html`)).href);
      assert.equal(await page.locator('.slide').count(), 15);
      for (let slide = 0; slide < 15; slide++) {
        await page.evaluate(n => show(n), slide);
        const metrics = await page.evaluate(() => ({ h: document.documentElement.scrollHeight, w:document.documentElement.scrollWidth, vh:innerHeight,vw:innerWidth }));
        if (metrics.w > metrics.vw + 2 || (size.width >= 1000 && metrics.h > metrics.vh + 2)) overflows.push({lesson,slide:slide+1,size,...metrics});
        checked++;
      }
      await page.evaluate(()=>show(0));
      await page.keyboard.press('ArrowRight');
      assert.equal(await page.locator('.page-count').textContent(), '2 / 15');
      await page.locator('#toc').click();
      assert.equal(await page.locator('dialog').evaluate(d=>d.open),true);
      await page.locator('.toc-list button').nth(3).click();
      assert.equal(await page.locator('.page-count').textContent(), '4 / 15');
      await page.locator('#notes').click();
      assert(await page.locator('.slide.active .teacher-note').isVisible());
      await page.locator('#notes').click();
      assert(!(await page.locator('.slide.active .teacher-note').isVisible()));
      const quizIndex = await page.locator('.slide').evaluateAll(xs=>xs.findIndex(x=>x.querySelector('.quiz')));
      await page.evaluate(n=>show(n),quizIndex);
      await page.locator('.slide.active .quiz button[data-correct=true]').first().click();
      assert((await page.locator('.slide.active .feedback').first().textContent()).includes('回答正确'));
      const answerIndex=await page.locator('.slide').evaluateAll(xs=>xs.findIndex(x=>x.querySelector('details')));
      await page.evaluate(n=>show(n),answerIndex);
      await page.locator('.slide.active summary').first().click();
      assert(await page.locator('.slide.active details').first().evaluate(d=>d.open));
      await page.reload();
      assert.equal(await page.locator('.page-count').textContent(),`${answerIndex+1} / 15`);
    }
  }
  await page.setViewportSize({width:1366,height:768});
  await page.goto(pathToFileURL(path.join(__dirname,'index.html')).href);
  assert.equal(await page.locator('.lesson-card').count(),4);
  for(const href of await page.locator('a').evaluateAll(xs=>xs.map(x=>x.getAttribute('href')))) assert(fs.existsSync(path.join(__dirname,href)),href);
  await page.screenshot({path:path.join(__dirname,'preview-index.png'),fullPage:true});
  await page.goto(pathToFileURL(path.join(__dirname,'lesson-04.html')).href+'#7');
  await page.screenshot({path:path.join(__dirname,'preview-relations.png'),fullPage:true});
  await page.emulateMedia({media:'print'});
  assert.equal(await page.locator('.slide').evaluateAll(xs=>xs.filter(s=>getComputedStyle(s).display!=='none').length),15);
  await browser.close();
  console.log(JSON.stringify({checked,errors,overflows},null,2));
  assert.equal(errors.length,0,'Browser JavaScript errors');
  assert.equal(overflows.length,0,'Slide overflow');
})().catch(e=>{console.error(e);process.exitCode=1;});

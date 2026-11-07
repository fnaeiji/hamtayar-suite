import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { mkdirSync } from 'node:fs';
const uiRoot = fileURLToPath(new URL('../../', import.meta.url));
const screenshots = resolve(uiRoot, 'runtime/browser-check');
mkdirSync(screenshots, { recursive: true });

(async () => {
  const records = [];
  const errors = [];
  const external = [];
  const results = [];
  const project = {
    id: 'demo-code',
    name: 'پروژه آزمون مرورگر',
    status: 'ready',
    active_index: 'active-demo',
    files: [{ path: 'src/sample.py', language: 'python', excluded: false }],
    accepted_files: 1,
    logs: ['fixture backend for browser verification'],
    counts: { nodes: 2, relationships: 1 },
  };
  const backend = http.createServer((req, res) => {
    records.push({ url: req.url, origin: req.headers.origin, method: req.method });
    res.setHeader('Content-Type', 'application/json');
    if (req.url === '/api/projects') return res.end(JSON.stringify([project]));
    if (req.url === '/api/archives/capabilities')
      return res.end(
        JSON.stringify({ rar_decoder: { available: true }, limits: { upload_mb: 1024 } }),
      );
    if (req.url === '/api/settings')
      return res.end(JSON.stringify({ values: {}, secrets_present: {} }));
    if (req.url === '/api/connection/test')
      return res.end(
        JSON.stringify({ destination: { ok: true }, staging: { ok: true } }),
      );
    if (req.url === '/api/capabilities') return res.end('[]');
    if (req.url === '/api/projects/demo-code') return res.end(JSON.stringify(project));
    if (
      req.url.startsWith('/api/projects/demo-code/graph/relations') ||
      req.url.startsWith('/api/projects/demo-code/graph/kinds')
    )
      return res.end('[]');
    if (req.url.startsWith('/api/projects/demo-code/graph'))
      return res.end(
        JSON.stringify({
          nodes: [
            { id: 'node-1', name: 'SampleClass', kind: 'Class', path: 'src/sample.py' },
            {
              id: 'node-2',
              name: 'sample_method',
              kind: 'Function',
              path: 'src/sample.py',
            },
          ],
          edges: [{ id: 'link-1', source: 'node-1', target: 'node-2', kind: 'CONTAINS' }],
          mode: 'overview',
          direction: 'both',
          depth: 2,
          truncated: false,
        }),
      );
    if (req.url.startsWith('/api/projects/demo-code/files'))
      return res.end(JSON.stringify({ files: project.files, total: 1 }));
    res.statusCode = 404;
    return res.end(JSON.stringify({ detail: 'Fixture route unavailable' }));
  });
  await new Promise((resolve) => backend.listen(8187, '127.0.0.1', resolve));
  const probe = http.createServer();
  await new Promise((resolve, reject) => {
    probe.once('error', reject);
    probe.listen(5179, '127.0.0.1', resolve);
  });
  await new Promise((resolve) => probe.close(resolve));
  const script = process.env.SMOKE_PREVIEW === '1' ? 'preview' : 'dev';
  const command = process.platform === 'win32' ? 'cmd.exe' : 'npm';
  const args =
    process.platform === 'win32'
      ? ['/c', `npm run ${script} -- --port 5179`]
      : ['run', script, '--', '--port', '5179'];
  const server = spawn(command, args, {
    cwd: uiRoot,
    stdio: 'ignore',
    detached: true,
    env: { ...process.env, CGC_API_TARGET: 'http://127.0.0.1:8187' },
  });
  let browser;
  try {
    for (let i = 0; i < 80; i++) {
      try {
        if ((await fetch('http://127.0.0.1:5179')).ok) break;
      } catch {
        // The owned Vite process may still be starting.
      }
      await new Promise((r) => setTimeout(r, 100));
    }
    browser = await chromium.launch({
      headless: true,
      ...(process.env.BROWSER_EXECUTABLE
        ? { executablePath: process.env.BROWSER_EXECUTABLE }
        : {}),
      args: ['--no-sandbox'],
    });
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
    page.on('pageerror', (e) => errors.push(e.message));
    page.on('request', (r) => {
      if (
        !r.url().startsWith('http://127.0.0.1:5179') &&
        !r.url().startsWith('data:') &&
        !r.url().startsWith('blob:')
      )
        external.push(r.url());
    });
    async function inspect(name) {
      await page.evaluate(() => document.fonts.ready);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      );
      if (overflow) throw Error(name + ' page overflow');
      results.push({ name, overflow });
    }
    await page.goto('http://127.0.0.1:5179');
    await page.getByLabel('نام کاربری').fill('demo');
    await page.getByLabel('گذرواژه').fill('Hamtayar123!');
    await page.getByRole('button', { name: 'ورود به محیط آزمایشی' }).click();
    await page.getByRole('heading', { name: 'به دموی همتایار خوش آمدید' }).waitFor();
    await inspect('overview-desktop');
    await page.screenshot({
      path: resolve(screenshots, 'unified-overview.png'),
      fullPage: true,
    });
    await page.getByRole('link', { name: 'پردازش اسناد سازمانی', exact: true }).click();
    await page.getByLabel('انتخاب اسناد').setInputFiles({
      name: 'guide.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from(
        'مدیریت دانش سازمانی در مرکز فناوری انجام می‌شود. عبارت اختصاصی کیمیاتست است.',
        'utf8',
      ),
    });
    await page.getByRole('textbox', { name: /^مرکز/ }).fill('مرکز فناوری');
    await page.getByRole('combobox', { name: /نوع سند/ }).selectOption('confidential');
    const card = page.getByRole('article', { name: 'guide.txt' });
    if ((await card.getByLabel('نام فایل', { exact: true }).inputValue()) !== 'guide.txt')
      throw Error('Missing file name facts');
    if (
      (await card.getByLabel('شناسه منبع', { exact: true }).count()) ||
      (await card.getByLabel('فضای دانشی', { exact: true }).count())
    )
      throw Error('Obsolete editable identifiers remain');
    await page.getByRole('button', { name: 'پیش‌نمایش درخواست', exact: true }).click();
    const documentPreview = page.getByRole('region', { name: 'پیش‌نمایش درخواست‌ها' });
    const selectedRequest = JSON.parse(
      await documentPreview.locator('pre').textContent(),
    )[0];
    if (
      'sourceId' in selectedRequest ||
      'knowledgeSpaceId' in selectedRequest ||
      selectedRequest.file.name !== 'guide.txt' ||
      !selectedRequest.file.size
    )
      throw Error('Document preview mismatch');
    await inspect('documents-desktop');
    await page.screenshot({
      path: resolve(screenshots, 'unified-documents.png'),
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await inspect('documents-mobile');
    await page.screenshot({
      path: resolve(screenshots, 'unified-documents-mobile.png'),
      fullPage: true,
    });
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.getByRole('button', { name: 'پردازش', exact: true }).click();
    await page.getByText('نتیجه نمایشی؛ داده در بک‌اند ثبت نمی‌شود').waitFor();
    await page
      .getByRole('link', { name: 'جستجو عبارت در اسناد سازمانی', exact: true })
      .click();
    await page.getByLabel('عبارت موردنظر').fill('کیمیاتست');
    await page.getByLabel('مرکز', { exact: true }).selectOption('مرکز فناوری');
    await page.getByLabel('نوع سند').selectOption('confidential');
    await page.getByRole('button', { name: 'پیش‌نمایش درخواست', exact: true }).click();
    const preview = page.getByRole('region', { name: 'پیش‌نمایش درخواست جستجو' });
    const request = JSON.parse(await preview.locator('pre').textContent());
    if (
      request.phrase !== 'کیمیاتست' ||
      request.filters.conditions.length !== 2 ||
      request.filters.conditions[1].value !== 'confidential'
    )
      throw Error('Search request preview mismatch');
    await page.getByRole('button', { name: 'جستجوی عبارت' }).click();
    await page.getByRole('heading', { name: 'guide.txt' }).waitFor();
    await page.locator('mark').getByText('کیمیاتست').waitFor();
    await inspect('phrase-search-desktop');
    await page.screenshot({
      path: resolve(screenshots, 'unified-search.png'),
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await inspect('phrase-search-mobile');
    await page.screenshot({
      path: resolve(screenshots, 'unified-search-mobile.png'),
      fullPage: true,
    });
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.getByRole('link', { name: 'پردازش کدبیس', exact: true }).click();
    const frame = page.frameLocator('iframe[title="همتایار کد — پردازش کدبیس"]');
    await frame.getByRole('heading', { name: 'نمای کلی کدبیس', exact: true }).waitFor();
    await frame.getByLabel('پروژه', { exact: true }).selectOption('demo-code');
    await page.getByRole('link', { name: 'مرور کد', exact: true }).click();
    await frame.getByRole('heading', { name: 'مرور کد', exact: true }).waitFor();
    if ((await frame.getByLabel('پروژه', { exact: true }).inputValue()) !== 'demo-code')
      throw Error('Project lost between submenus');
    await page.getByRole('link', { name: 'کاوش گراف', exact: true }).click();
    await frame.getByRole('heading', { name: 'کاوش گراف', exact: true }).waitFor();
    await frame.locator('.graph-canvas').waitFor();
    await inspect('embedded-graph-desktop');
    await page.screenshot({
      path: resolve(screenshots, 'unified-code-graph.png'),
      fullPage: true,
    });
    await page.getByRole('link', { name: 'تنظیمات و قابلیت‌ها', exact: true }).click();
    await frame
      .getByRole('heading', { name: 'تنظیمات و قابلیت‌ها', exact: true })
      .waitFor();
    await frame.getByLabel('LLM_MODEL', { exact: true }).fill('unsaved-browser-test');
    await frame.getByRole('button', { name: 'تست Neo4j مقصد و staging' }).click();
    await page.getByRole('link', { name: 'جستجو و تحلیل کد', exact: true }).click();
    await frame.getByRole('heading', { name: 'جستجو و تحلیل کد', exact: true }).waitFor();
    await page.getByRole('link', { name: 'تنظیمات و قابلیت‌ها', exact: true }).click();
    await frame
      .getByRole('heading', { name: 'تنظیمات و قابلیت‌ها', exact: true })
      .waitFor();
    if (
      (await frame.getByLabel('LLM_MODEL', { exact: true }).inputValue()) !==
      'unsaved-browser-test'
    )
      throw Error('Frame remounted between submenus');
    await page.setViewportSize({ width: 390, height: 844 });
    await inspect('embedded-code-mobile');
    const frameOverflow = await frame
      .locator('body')
      .evaluate(() => document.documentElement.scrollWidth > innerWidth);
    if (frameOverflow) throw Error('Embedded mobile frame overflow');
    await page.screenshot({
      path: resolve(screenshots, 'unified-code-mobile.png'),
      fullPage: true,
    });
    if (
      !records.some(
        (r) => r.url === '/api/connection/test' && r.origin === 'http://127.0.0.1:5179',
      )
    )
      throw Error('No actual proxy request with preserved browser origin');
    if (errors.length) throw Error(errors.join('\n'));
    if (external.length) throw Error('External origin requested ' + external.join(','));
    console.log(
      JSON.stringify(
        {
          results,
          frameOverflow,
          pageErrors: errors,
          externalRequests: external,
          proxyRequests: records.length,
          preservedProject: true,
          preservedSettingsDraft: true,
        },
        null,
        2,
      ),
    );
  } finally {
    if (browser) await browser.close();
    if (process.platform === 'win32')
      spawn('taskkill', ['/pid', String(server.pid), '/T', '/F']);
    else process.kill(-server.pid, 'SIGTERM');
    backend.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

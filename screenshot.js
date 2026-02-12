#!/usr/bin/env node
/**
 * Docker 私有仓库管理系统 - 界面截图脚本
 * 使用 Puppeteer 进行截图
 */

const puppeteer = require('puppeteer');

async function takeScreenshot(url, outputFile = 'screenshot.png', width = 1400, height = 1100) {
    console.log('正在启动浏览器...');
    console.log(`目标地址: ${url}`);

    try {
        const browser = await puppeteer.launch({
            headless: 'new',
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        });

        const page = await browser.newPage();
        await page.setViewport({ width, height });
        await page.setUserAgent('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36');

        console.log('浏览器已启动');
        console.log('正在加载页面...');
        await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
        console.log('页面加载完成');

        console.log('等待页面元素渲染...');
        try {
            await page.waitForSelector('header.header', { timeout: 10000 });
            console.log('页面主体已加载');
        } catch (error) {
            console.log('警告：页面主体加载超时，继续截图');
        }

        console.log('等待页面完全渲染（3秒）...');
        await new Promise(resolve => setTimeout(resolve, 3000));

        console.log(`正在截图，保存为 ${outputFile}...`);
        await page.screenshot({ path: outputFile, fullPage: false, type: 'png' });
        console.log(`✓ 截图成功！文件已保存: ${outputFile}`);

        await browser.close();
        console.log('浏览器已关闭');
        return true;

    } catch (error) {
        console.error(`✗ 截图失败: ${error.message}`);
        return false;
    }
}

async function main() {
    const TARGET_URL = 'http://192.168.5.249:8080';
    const OUTPUT_FILE = 'screenshot.png';

    console.log('='.repeat(50));
    console.log('Docker 私有仓库管理系统 - 界面截图工具');
    console.log('='.repeat(50));

    const success = await takeScreenshot(TARGET_URL, OUTPUT_FILE);

    if (success) {
        console.log('\n' + '='.repeat(50));
        console.log('截图任务完成！');
        console.log('='.repeat(50));
        process.exit(0);
    } else {
        console.log('\n' + '='.repeat(50));
        console.log('截图任务失败');
        console.log('='.repeat(50));
        process.exit(1);
    }
}

main();

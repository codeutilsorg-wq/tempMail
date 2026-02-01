const puppeteer = require('puppeteer');
const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

async function generateEasyTempInboxOG() {
  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body {
          margin: 0;
          padding: 0;
          width: 1200px;
          height: 630px;
          display: flex;
          flex-direction: column;
          justify-content: center;
          align-items: center;
          background: linear-gradient(135deg, #4a90e2 0%, #6db3f2 100%);
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
        }
        .icon {
          font-size: 140px;
          margin-bottom: 30px;
          filter: drop-shadow(0 4px 8px rgba(0,0,0,0.15));
        }
        h1 {
          font-size: 96px;
          color: #ffffff;
          margin: 0 0 20px 0;
          font-weight: 700;
          text-align: center;
          text-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }
        .tagline {
          font-size: 44px;
          color: rgba(255, 255, 255, 0.95);
          margin: 0 0 50px 0;
          font-weight: 400;
          text-align: center;
        }
        .features {
          font-size: 32px;
          color: rgba(255, 255, 255, 0.85);
          margin: 20px 0;
          text-align: center;
          font-weight: 300;
        }
        .url {
          font-size: 30px;
          color: rgba(255, 255, 255, 0.7);
          margin-top: 40px;
          font-weight: 300;
        }
      </style>
    </head>
    <body>
      <div class="icon">📬</div>
      <h1>EasyTempInbox</h1>
      <div class="tagline">Free Temporary Email Service</div>
      <div class="features">No Signup • Auto-Delete • Privacy Protected</div>
      <div class="url">www.easytempinbox.com</div>
    </body>
    </html>
  `;

  console.log('🚀 Launching browser...');
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1200, height: 630 });

  console.log('📄 Rendering HTML...');
  await page.setContent(html, { waitUntil: 'networkidle0' });

  console.log('📸 Taking screenshot...');
  const screenshot = await page.screenshot({ type: 'png' });
  await browser.close();

  // Ensure images directory exists
  const imagesDir = path.join(__dirname, 'frontend', 'images');
  if (!fs.existsSync(imagesDir)) {
    fs.mkdirSync(imagesDir, { recursive: true });
  }

  const outputPath = path.join(imagesDir, 'og-image.png');

  console.log('🎨 Optimizing image...');
  await sharp(screenshot)
    .png({ quality: 90, compressionLevel: 9 })
    .toFile(outputPath);

  // Get file size
  const stats = fs.statSync(outputPath);
  const fileSizeKB = (stats.size / 1024).toFixed(2);

  console.log('\n✅ OG Image generated successfully!');
  console.log(`📁 Location: ${outputPath}`);
  console.log(`📏 Size: 1200 x 630 pixels`);
  console.log(`💾 File size: ${fileSizeKB} KB`);
  console.log('\n🔍 Next steps:');
  console.log('1. View the image at: frontend/images/og-image.png');
  console.log('2. Test on social media validators:');
  console.log('   - Facebook: https://developers.facebook.com/tools/debug/');
  console.log('   - Twitter: https://cards-dev.twitter.com/validator');
  console.log('3. Deploy to production');
}

// Run the generator
generateEasyTempInboxOG().catch(error => {
  console.error('❌ Error generating OG image:', error);
  process.exit(1);
});

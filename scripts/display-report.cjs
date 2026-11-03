// Same decisions as the browser, for the Actions artifact or local inspection.
const fs = require('node:fs');
const path = require('node:path');
const display = require('../web/display.js');
const root = path.resolve(__dirname, '..');
const data = JSON.parse(fs.readFileSync(process.argv[2] || path.join(root, 'data/articles.json'), 'utf8'));
const rules = JSON.parse(fs.readFileSync(process.argv[4] || path.join(root, 'config/rules.json'), 'utf8'));
console.log(JSON.stringify(display.report(data.articles, rules.display, process.argv[3]), null, 2));

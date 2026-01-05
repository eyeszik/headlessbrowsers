# CLAUDE.md - Project Documentation for Claude Code

## Project Overview

**Headless Browsers** is a curated documentation repository that maintains a comprehensive list of headless web browsers and browser automation tools. A headless browser is a web browser without a graphical user interface that can be controlled programmatically, used for automation, testing, web scraping, and other purposes.

## Repository Information

- **Type**: Documentation/Curated List Repository
- **Primary File**: README.md
- **Owner**: dhamaniasad
- **Sponsors**: Browserbase, Bright Data
- **License**: See LICENSE file

## Project Structure

```
.
├── .github/
│   └── FUNDING.yml          # GitHub sponsors configuration
├── .git/                    # Git repository data
├── LICENSE                  # Project license
└── README.md               # Main curated list of headless browsers
```

## Content Categories

The README.md organizes headless browsers into the following categories:

1. **Browser Engines** - Full rendering engines (Chromium Embedded Framework, Erik, jBrowserDriver, PhantomJS, Splash, Surf)
2. **Multi Drivers** - Libraries controlling multiple browser engines (CasperJS, Geb, Playwright variants, Selenium, Splinter, SST, Watir)
3. **PhantomJS Drivers** - Tools specifically for PhantomJS (Ghostbuster, jedi-crawler, Lotte, phantompy, X-RAY, Horseman)
4. **Chromium Drivers** - Chrome/Chromium automation (Awesomium, Puppeteer variants, chrome-remote-interface, chromedp, Chromeless, Wendigo, cdp4j, Pyppeteer)
5. **Webkit Drivers** - WebKit-based tools (Browserjet, ghost.py, Jasmine-Headless-Webkit, wkhtmltopdf, WKZombie)
6. **Other Drivers** - Alternative browser engines (Cypress, Nightmare, SlimerJS, SpecterJS, trifleJS)
7. **Fake Browser Engine** - HTML-only/naive browsers (AngleSharp, HtmlUnit, JSDom, MechanicalSoup, mechanize, SimpleBrowser, Zombie.js)
8. **Runs in a Browser** - Testing tools that run within browsers (TestCafé, Sahi, WatiN)
9. **Misc Tools** - Supporting tools (browser-launcher, Headless Recorder)

## Key Information for Each Entry

Each headless browser entry includes:
- **Name** - Tool name with link to repository/website
- **About** - Brief description
- **Supported Languages** - Programming languages supported
- **License** - Open source license or commercial status

## Maintenance Status

Some entries are marked as:
- `[[Unmaintained]]` - Projects that are no longer actively developed (e.g., PhantomJS, CasperJS)

## Project Purpose

This repository serves as:
- A reference guide for developers choosing headless browser solutions
- A comprehensive catalog of browser automation tools across different languages
- A historical record of headless browser technology evolution

## Contributing Context

When making updates to this project:
- Maintain the existing table format in README.md
- Ensure new entries include all four columns (Name, About, Supported Languages, License)
- Mark unmaintained projects appropriately
- Keep entries alphabetically organized within categories
- Verify links are functional before adding

## No Code, Pure Documentation

This is a documentation-only repository with:
- No source code to test or compile
- No dependencies to manage
- No build process
- No automated tests

Focus is entirely on maintaining accurate, up-to-date information about headless browser tools.

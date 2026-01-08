# Contributing to Headless Browsers

Thank you for your interest in contributing to this curated list of headless web browsers! This guide will help you submit high-quality additions and updates.

## How to Contribute

### Adding a New Entry

1. **Check for duplicates** - Search the README.md to ensure the tool isn't already listed
2. **Choose the correct category** - Place your entry in the most appropriate section:
   - **Browser Engines** - Full rendering engines with JavaScript execution
   - **Multi Drivers** - Libraries that control multiple browser engines
   - **PhantomJS Drivers** - Tools specifically for PhantomJS
   - **Chromium Drivers** - Chrome/Chromium automation tools
   - **Webkit Drivers** - WebKit-based tools
   - **Other Drivers** - Alternative browser engines (Firefox, IE, etc.)
   - **Fake Browser Engine** - HTML-only/naive browsers without full rendering
   - **Runs in a Browser** - Testing tools that execute within browsers
   - **Misc Tools** - Supporting utilities

3. **Follow the entry format** - Each entry must include all four columns:

```markdown
|[Tool Name](https://github.com/user/repo) | Brief description of what it does | Language1, Language2 | License |
```

### Entry Requirements

#### Name Column
- Must link to the project's primary repository or official website
- Use the official project name with correct capitalization

#### About Column
- Keep descriptions concise (1-2 sentences)
- Focus on what makes the tool unique or its primary use case
- Avoid marketing language - be factual and neutral

#### Supported Languages Column
- List all programming languages that can use the tool
- Use official language names (JavaScript, not JS)
- Separate multiple languages with commas
- Order by popularity/primary language first

#### License Column
- Use official license name (MIT, Apache 2.0, GPL-3.0, etc.)
- If commercial, specify "Commercial" or "Free/Commercial"
- If not specified in the repository, use "Not specified"
- For unmaintained projects, maintain existing license info

### Maintaining Quality

#### Mark Unmaintained Projects
If a project is no longer maintained:
- Add `[[Unmaintained]]` tag before the description
- Link to an official announcement if available
- Example: `[[Unmaintained]](https://github.com/project/issues/123)`

#### Keep Alphabetical Order
- Within each category, entries should be alphabetically ordered by name
- This helps users quickly find specific tools

#### Verify Links
- Ensure all links are working before submitting
- Use the primary repository (GitHub, GitLab, etc.) when available
- Use official website if no public repository exists

## Submission Process

1. **Fork the repository**
2. **Create a new branch** - Use a descriptive name like `add-newtool` or `update-puppeteer`
3. **Make your changes** - Add or update entries in README.md
4. **Test your changes** - Verify markdown renders correctly
5. **Submit a Pull Request** with:
   - Clear title describing the change
   - Brief description of what you're adding/updating
   - Link to the tool's repository for new entries

## Updating Existing Entries

Help keep this list current by:
- Updating outdated descriptions
- Fixing broken links
- Adding unmaintained markers to abandoned projects
- Correcting license information
- Updating language support

## What NOT to Submit

Please avoid:
- Personal projects without significant community adoption
- Duplicate tools (check thoroughly first)
- Tools that are primarily testing frameworks without headless capabilities
- Commercial-only tools without free tiers (unless already listed)
- Tools in alpha/early development without stable releases

## Questions?

If you're unsure about:
- Which category fits your tool
- Whether a tool qualifies for inclusion
- How to format your entry

Feel free to open an issue for discussion before submitting a PR.

## Code of Conduct

Be respectful and constructive in all interactions. This is a collaborative project to help the developer community.

---

Thank you for helping maintain this valuable resource for the developer community!

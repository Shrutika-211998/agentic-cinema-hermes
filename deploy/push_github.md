# Publish Second Unit to GitHub

`gh` is installed at `C:\Users\shrut\tools\bin\gh.exe` but not logged in yet.

## Option A — gh CLI (recommended)

1. Create a classic PAT with **repo** scope: https://github.com/settings/tokens  
2. In a terminal:

```bash
export PATH="/c/Users/shrut/tools/bin:$PATH"
cd C:/Users/shrut/second-unit
echo YOUR_GITHUB_TOKEN | gh auth login --with-token
gh repo create second-unit --public --source=. --remote=origin --push \
  --description "Second Unit — autonomous studio crew for rights-cleared cuts (Agentic Cinema / Google Cloud)"
gh repo edit --add-topic "agentic-ai,google-cloud,gemini,adk,hackathon,mcp"
```

## Option B — manual

1. Create empty public repo `second-unit` on GitHub (Apache-2.0).
2. Push:

```bash
cd C:/Users/shrut/second-unit
git remote add origin https://github.com/YOUR_USER/second-unit.git
git push -u origin main
```

Then paste the repo URL into Devpost + set LICENSE visible in About.

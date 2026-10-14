# Credentials and GitHub environments

Use separate `staging` and `production` environments in each repository. Only `main` is allowed, and a required owner review gates jobs referencing that environment. Self-review is allowed for this one-person project so it does not deadlock. When another maintainer joins, require independent review. Environment protection is not hosting: no server or paid resource is provisioned.

## Store values directly in GitHub

Open repository **Settings → Environments → staging (or production) → Environment secrets → Add environment secret**. Never paste credentials into issues, PRs, Markdown, workflow YAML, or chat.

In the main Copilot repository, prepare these names:

| Name | GitHub storage | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Environment secret | Backend database connection string, including its password |
| `OPENAI_API_KEY` | Environment secret | Required only when the selected provider is OpenAI |
| `ANTHROPIC_API_KEY` | Environment secret | Required only when the selected provider is Anthropic |
| `LLM_PROVIDER` | Environment variable | `openai` or `anthropic`; defaults to `openai` |
| `APP_ENV` | Environment variable | `staging` or `production` |

Only add the provider key you use. Demo repositories use synthetic fixtures and need no model or database credentials. Do not copy production keys into demos.

CLI alternative: run these locally; `gh secret set` prompts for the value without putting it in the command itself:

```sh
gh secret set DATABASE_URL --repo r-kovalenko/api-contract-copilot --env staging
gh secret set OPENAI_API_KEY --repo r-kovalenko/api-contract-copilot --env staging
gh variable set LLM_PROVIDER --body openai --repo r-kovalenko/api-contract-copilot --env staging
```

Repeat for `production` with different credentials. No placeholder or real secret values are created by repository setup. GitHub will not return secret values after they are saved.

## Runtime use

The manual **Check environment configuration** workflow runs only from `main`, requires the selected environment review, and checks that required names are nonempty. It never prints values, connects to a database, calls a model, or deploys anything. Its presence check does not prove credentials are valid. Ordinary CI never receives these secrets.

In a future deployment job, bind `environment: staging` or `environment: production`, inject `${{ secrets.NAME }}` into only the step that needs it, and pass it to the hosting provider's server-side secret store. Prefer OIDC for cloud authentication instead of a persistent cloud access key. Configure the trust policy for the exact repository and environment once the host is chosen.

GitHub environment secrets do not automatically become a local `.env`, a container's runtime environment, or a deployed application's configuration. The deployment integration must explicitly deliver them. Never put secrets in Docker `ARG`/`ENV` build layers, frontend `VITE_*` variables, command traces, or uploaded artifacts. Do not generate a `.env` artifact in CI.

## Local development and rotation

Copy `.env.example` to `.env`, set a unique local `POSTGRES_PASSWORD`, and keep the populated file ignored. Environment files are local plaintext configuration, not encrypted storage. Compose reads the local database values; the future application configuration layer will load runtime provider/database settings. Keep separate credentials for every environment with the minimum permissions and provider budget needed.

If a credential leaks, revoke/rotate it at the provider, update GitHub and the runtime secret store, and review usage. Removing the current file or masking logs does not revoke the credential or erase Git history. GitHub push protection and Gitleaks reduce accidental exposure; neither replaces rotation.

References: [GitHub environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments), [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html).

# Action JSON language server in an editor

`webrunner-lsp` (the same as `python -m je_web_runner.action_lsp`) is a language server for action
JSON files. It talks LSP over stdio and offers completion (command names, a command's parameter
names, variable names after `${`), hover, diagnostics from the action linter, a quick fix for legacy
command names and Format Document.

Every editor needs the same three facts:

| What | Value |
|---|---|
| Command | `webrunner-lsp` (or `<python> -m je_web_runner.action_lsp` with the interpreter that has `je_web_runner`) |
| Transport | stdio |
| Documents | the JSON files that are action files, for example `actions/**/*.json` |

The server lints every document it is given as an action file, so attach it to your action
directories only, not to every `.json` file of the project.

## Neovim (built-in client)

```lua
vim.api.nvim_create_autocmd({ "BufReadPost", "BufNewFile" }, {
  pattern = { "*/actions/*.json", "*/actions/**/*.json" },
  callback = function(args)
    vim.lsp.start({
      name = "webrunner-lsp",
      cmd = { "webrunner-lsp" },
      root_dir = vim.fs.dirname(vim.fs.find({ "webrunner.toml", "pyproject.toml", ".git" },
        { upward = true, path = vim.api.nvim_buf_get_name(args.buf) })[1]),
    })
  end,
})
```

## Helix (`languages.toml`)

```toml
[language-server.webrunner-lsp]
command = "webrunner-lsp"

[[language]]
name = "json"
language-servers = ["vscode-json-language-server", "webrunner-lsp"]
```

Helix attaches a server by language, so this one sees every JSON file; keep it in a project-local
`.helix/languages.toml` of a project whose JSON files are action files.

## VS Code and JetBrains IDEs

Neither has a built-in client for an arbitrary language server, and this repository ships no
extension. Install a generic LSP client extension or plugin and give it the three facts above. The
JSON schema mapping in `vscode-settings.example.json` and `jetbrains-jsonschemamapping.example.xml`
needs no extension and can be used alongside: the schema checks the shape of a file, the language
server adds what the schema cannot know (the live command table, parameters, variables, lint rules).

These editor snippets were written from the editors' documented configuration and have not been
tried by this project's tests; the server itself is tested over stdio
(`test/integration_test/test_action_lsp_subprocess.py`).

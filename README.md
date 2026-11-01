# EnvRef Map

**An offline CLI that maps environment-variable references in source code to safe example templates.**

EnvRef Map helps catch a common setup drift: code starts reading a variable, but the project's example template does not mention it. It reports the variable name and source location, then compares references with `.env.example`, `.env.sample`, and `.env.template` files.

## Install

```sh
git clone https://github.com/erburenwang/envref-map.git
cd envref-map
python -m pip install .
```

Python 3.11 or newer is required. The installed CLI has no runtime dependencies.

## Quick start

```sh
envref-map scan
envref-map scan --root ./services/api --format markdown
envref-map scan --root . --strict --format json
envref-map scan --root . --template config/local.example
```

The default report goes to standard output. Normal mode returns success when a report is produced, even when keys are missing. Use `--strict` in CI to return a failure for missing template keys.

Example:

```text
Missing keys:
  PAYMENT_API_URL — src/payments/client.ts:18
```

Reports include names, root-relative paths, and line numbers. They never include assignment values or source-line contents.

## What it scans

Supported source extensions are `.py`, `.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`, `.tsx`, `.sh`, and `.bash`.

| Language | Static patterns |
|---|---|
| Python | `os.getenv("KEY")`, `os.environ.get("KEY")`, `os.environ["KEY"]` |
| JavaScript / TypeScript | `process.env.KEY`, `process.env["KEY"]`, `import.meta.env.KEY`, `import.meta.env["KEY"]` |
| Shell | `$KEY`, `${KEY}`, `${KEY:-default}`, `${KEY:?message}` |

Comments and ordinary strings are ignored. JavaScript template expressions are scanned, while template text and regular-expression bodies are ignored. Computed lookups such as `process.env[name]`, `os.getenv(name)`, and shell indirect expansion such as `${!PREFIX}` are reported as dynamic where recognizable; EnvRef Map does not guess their keys.

The scanner skips `.git`, `node_modules`, common virtual-environment and build directories, and symlinked files or directories. Results are sorted for repeatable text, Markdown, and JSON output.

Source and template text is read as UTF-8; a UTF-8 BOM is accepted. Files containing NUL characters are skipped with a value-free binary-file diagnostic. This conservative marker check does not identify every binary format.

## Templates and privacy

Automatic discovery recognizes only these exact filenames:

- `.env.example`
- `.env.sample`
- `.env.template`

Use `--template PATH` to include a differently named example. A custom template must end in `.example`, `.sample`, or `.template`. Its resolved path, including a symlink target, must stay inside `--root`. Real `.env` and other `.env.*` files are rejected even when explicitly passed.

EnvRef Map is offline and read-only. It does not access a network, run subprocesses, modify the scanned project, or store environment values. Template parsing extracts assignment names and discards values. The tool does not decide whether a variable is secret, required, valid, or configured correctly.

Static scanning cannot find every runtime lookup. Dynamic construction, framework-specific configuration loaders, and syntax outside the supported patterns may be missed. A documented key only means its name appears in an example template; it does not validate the value.

## Output and exit codes

```text
envref-map scan [--root PATH] [--template PATH ...] [--format text|markdown|json] [--strict]
```

- `text` is the default. `markdown` is suitable for reviews. `json` uses schema version 1 and includes scanned-file count, template paths, referenced keys and locations, unused template keys, dynamic-access notes, and diagnostics.
- `0`: report produced; in strict mode, no referenced key is missing.
- `1`: strict mode found a missing key, or scanning produced a diagnostic/error.
- `2`: invalid command-line arguments.

## Development

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidance.

---

# EnvRef Map（中文）

所有模板和源码文本均按 UTF-8 读取，支持 UTF-8 BOM；检测到 NUL 字符时，文件会按二进制输入跳过，并给出不含文件内容的诊断。这项保守检查只识别常见的二进制标记，不能识别所有二进制格式。

**离线扫描源码中的环境变量引用，并与安全示例模板对照。**

代码新增了环境变量读取，但 `.env.example` 没同步，是常见的部署问题。EnvRef Map 会列出变量名和源码位置，并与 `.env.example`、`.env.sample`、`.env.template` 对照，找出缺失项和模板中的闲置项。

## 安装

```sh
git clone https://github.com/erburenwang/envref-map.git
cd envref-map
python -m pip install .
```

需要 Python 3.11 或更新版本。安装后的命令没有运行时依赖。

## 快速使用

```sh
envref-map scan
envref-map scan --root ./services/api --format markdown
envref-map scan --root . --strict --format json
envref-map scan --root . --template config/local.example
```

默认将报告输出到标准输出。普通模式只要成功生成报告就返回成功，即使存在缺失项；在 CI 中使用 `--strict`，缺少模板键时返回失败。

报告只包含变量名、项目根目录内的相对路径和行号，不会输出赋值内容或源码行。

## 扫描范围

支持 `.py`、`.js`、`.jsx`、`.mjs`、`.cjs`、`.ts`、`.tsx`、`.sh`、`.bash` 文件。

| 语言 | 静态模式 |
|---|---|
| Python | `os.getenv("KEY")`、`os.environ.get("KEY")`、`os.environ["KEY"]` |
| JavaScript / TypeScript | `process.env.KEY`、`process.env["KEY"]`、`import.meta.env.KEY`、`import.meta.env["KEY"]` |
| Shell | `$KEY`、`${KEY}`、`${KEY:-default}`、`${KEY:?message}` |

扫描器会忽略注释和普通字符串；会扫描 JavaScript 模板字符串中的表达式，但忽略模板文本和正则表达式正文。对于 `process.env[name]`、`os.getenv(name)`、`${!PREFIX}` 等可识别的动态读取，会单独提示，但不会猜测变量名。

扫描器会跳过 `.git`、`node_modules`、常见虚拟环境和构建目录，以及符号链接文件和目录。文本、Markdown、JSON 结果均按稳定顺序排列。

## 模板与隐私

自动识别的文件名只有 `.env.example`、`.env.sample` 和 `.env.template`。自定义模板通过 `--template PATH` 指定，文件名必须以 `.example`、`.sample` 或 `.template` 结尾；解析后的路径（包括符号链接目标）必须留在 `--root` 之内。真实 `.env` 和其他 `.env.*` 文件即使被显式传入也会拒绝。

EnvRef Map 离线、只读：不联网、不运行子进程、不修改被扫描的项目，也不保存环境变量值。解析模板时只提取赋值名，不保留值。工具不会判断变量是否为机密、是否必需或配置是否正确。

静态扫描无法覆盖所有运行时读取方式。动态拼接、框架专用配置加载器和支持范围以外的语法可能被遗漏。变量名出现在示例模板中，只表示名称存在，不代表值有效。

## 输出与退出码

`--format` 支持 `text`（默认）、`markdown` 和 `json`。JSON 使用 schema version 1，包含扫描文件数、模板路径、变量名及源码位置、未使用模板键、动态访问提示和诊断信息。

- `0`：报告已生成；严格模式下没有缺失键。
- `1`：严格模式发现缺失键，或扫描产生诊断/错误。
- `2`：命令行参数无效。

## 开发

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

贡献方式见 [CONTRIBUTING.md](CONTRIBUTING.md)。

# Ubuntu Modern Toolchain Validation

状态：发布前验证说明；本文件描述目标环境与可复现步骤，不把未运行的目标写成已验证结论。

## Current / Supported / Not Supported / Future Work

| Category | Scope |
| --- | --- |
| Current target | Ubuntu 24.04 LTS or newer, CMake 3.24+, GCC 13+（推荐 GCC 14）、SystemC 3.0.2、C++17 default、C++20 smoke、Python 3.13 / 3.14。 |
| Supported after recorded evidence | 只有 `artifacts/ubuntu-validation/<run-id>/summary.md` 记录 PASS 的 host/configuration 才能写为 validated。 |
| Compatibility | SystemC 2.3.4 可用于旧版 SystemC compatibility experiments；它不是新 book baseline 的默认推荐。 |
| Not Supported | C++23 只是 optional experimental compatibility；GCC 16 不是最低要求。 |
| Future Work | 在可用 Ubuntu runner 上补充 GCC 14/15/16、SystemC 2.3.4 和 C++23 的独立矩阵记录。 |

本仓库的 LT/AT 模型仍是 bounded architecture performance experiments；toolchain
verification 不增加 cycle-accurate、protocol-compliance、silicon-validation 或
production-signoff claim。

## SystemC 3.0.2 primary installation

安装在用户目录，不下载或写入本仓库：

```bash
cd ~/workspace
wget https://www.accellera.org/images/downloads/standards/systemc/systemc-3.0.2.tar.gz
tar xf systemc-3.0.2.tar.gz
cd systemc-3.0.2
cmake -S . -B build \
  -DCMAKE_INSTALL_PREFIX="$HOME/local/systemc-3.0.2" \
  -DCMAKE_CXX_STANDARD=17 \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"
cmake --install build
export SYSTEMC_HOME="$HOME/local/systemc-3.0.2"
export LD_LIBRARY_PATH="$SYSTEMC_HOME/lib:$SYSTEMC_HOME/lib-linux64:$LD_LIBRARY_PATH"
```

`SYSTEMC_ROOT`、`SYSTEMC_HOME`、`USER_SYSTEMC_ROOT`、`CMAKE_PREFIX_PATH`、
`SystemC_DIR` 都可作为 prefix/configuration 输入。旧脚本仍可使用
`USER_SYSTEMC_INCLUDE_DIR` 和 `USER_SYSTEMC_LIB_DIR`；新 CMake resolver 会将 header
与 library 配对，并统一导出 `SystemC::systemc`。

SystemC ABI 必须与 consuming target 的 C++ standard 匹配。`AT_CXX17_SYSTEMC`
使用 `SYSTEMC_HOME`；`AT_CXX20_SYSTEMC` 只在设置 `SYSTEMC_HOME_CXX20` 时运行，
该路径应指向使用 C++20 重新编译安装的 SystemC。若只设置了 `SYSTEMC_HOME`，
脚本会把 `AT_CXX20_SYSTEMC` 标为 `SKIP`，避免 C++20 lab 链接 C++17 SystemC
导致 `sc_api_version` ABI mismatch。

## Python 3.13 / 3.14

Ubuntu validation 可以使用当前系统实际可安装的解释器。若 `python3.14` 不在 apt
source 中，使用 pyenv 或发行版提供的等价安装方式；不要把解释器绝对路径写入仓库。

```bash
PYTHON=python3.13 VENV_DIR=artifacts/venv/py313 bash scripts/setup_python_env.sh
PYTHON=python3.14 VENV_DIR=artifacts/venv/py314 bash scripts/setup_python_env.sh
```

`requirements.txt` 仅保留 portfolio-card rendering 的可选 `matplotlib`。没有被
checked-in workflow 使用的 pytest、ruff 或 mypy 不会被强行加入开发依赖。

## Ubuntu baseline and matrix command

`scripts/ubuntu_verify.sh` 不执行 sudo、不自动 apt install，并为每次运行创建独立的
ignored artifact tree。它会构建 standalone LT C++17 baseline；只有成功发现 SystemC
后才构建 AT C++17；required C++20 smoke 需要额外提供 `SYSTEMC_HOME_CXX20`。
Verilator 保持 OFF。

```bash
SYSTEMC_HOME="$HOME/local/systemc-3.0.2" \
SYSTEMC_HOME_CXX20="$HOME/local/systemc-3.0.2-cxx20" \
PYTHON=python3.13 \
RUN_ID=ubuntu2404-systemc302-gcc14-py313 \
bash scripts/ubuntu_verify.sh

cat artifacts/ubuntu-validation/ubuntu2404-systemc302-gcc14-py313/summary.md
```

脚本记录 `lsb_release`、kernel、CMake、compiler、Python、SystemC 输入变量，以及：

| Check | Required behavior |
| --- | --- |
| `LT_CXX17` | standalone LT baseline，缺失 SystemC 不应阻塞此项。 |
| `AT_CXX17_SYSTEMC` | 使用 `SYSTEMC_HOME`；SystemC 不可用时 `SKIP`，可用时 configure/build 必须 PASS。 |
| `AT_CXX20_SYSTEMC` | 使用 `SYSTEMC_HOME_CXX20`；未提供时 `SKIP`，提供后运行 required smoke。 |
| `PYTHON_COMPILE` | 使用 `PYTHONPYCACHEPREFIX`，bytecode 只写入本次 artifact tree。 |
| `SENSITIVE_SCAN` | 输出写入 artifact tree；发现旧用户名/旧仓库标识时 FAIL。 |

C++23、GCC 15/16、SystemC 2.3.4 和 Verilator 都是单独的 optional compatibility rows，
不能替代 primary SystemC 3.0.2 + C++17/C++20 evidence。

## Artifact and packaging policy

验证输出必须在 `artifacts/ubuntu-validation/<run-id>/` 或 `/tmp`。该脚本不运行会把
CSV、trace 或 report 写回 `examples/*/results/` 的 demo wrappers。

从 macOS 打包到 Ubuntu 时，使用：

```bash
tar --disable-copyfile --no-xattrs -czf systemc-tlm-performance-labs.tar.gz \
  systemc-tlm-performance-labs
```

这会避免 resource fork、xattrs 与 `._*` 文件污染源码。

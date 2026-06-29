# 案件处理启动器

集成多个案件处理工具的统一启动器，方便快捷地管理案件信息和调用各种处理工具。

## 功能特性

- 📋 **案件数据管理** - 保存/加载案件基本信息（保单号、伤者、出险信息等）
- 🛠️ **工具集成** - 集成5个常用工具：
  - 报告生成
  - 报告标准化
  - 目录工具
  - MD转DOCX
  - 结案审批表
- 📂 **一键执行** - 可选择执行单个或批量执行所有工具
- 💾 **数据共享** - 通过 `case-data.json` 在工具间共享案件数据

## 安装与运行

### 1. 安装依赖

```bash
cd 案件处理启动器
npm install
```

### 2. 放置工具文件

将你的 `.exe` 工具文件放入 `tools` 文件夹中：

```
案件处理启动器/
├── tools/
│   ├── 报告标准化工具.exe
│   ├── 报告生成.exe
│   ├── 附件md转docx工具.exe
│   ├── 结案审批表工具.exe
│   └── 目录工具.exe
├── main.js
├── index.html
├── ...
```

支持的工具文件名：
- `报告标准化工具.exe` / `报告标准化工具` / `report-standard.exe`
- `报告生成.exe` / `报告生成` / `report-generate.exe`
- `附件md转docx工具.exe` / `附件md转docx工具` / `md-to-docx.exe`
- `结案审批表工具.exe` / `结案审批表工具` / `approval-form.exe`
- `目录工具.exe` / `目录工具` / `catalog-tool.exe`

### 3. 运行

```bash
npm start
```

### 4. 打包为独立程序

```bash
npm install --save-dev electron-builder
npm run dist
```

打包后的程序将生成在 `dist` 文件夹中。

## 数据共享

工具通过 `case-data.json` 文件共享数据：

```json
{
  "caseId": "CASE-2026-001",
  "policyNo": "T260314800116400137332",
  "insured": "淮安金蜻蜓网络科技有限公司",
  "injured": "李小子",
  "thirdParty": "王攀",
  "accidentDate": "2026-03-14 07:17:20",
  "accidentLocation": "深圳市福田区滨河大道",
  "attachments": [
    "附件一：公估委托单",
    "附件二：电子保险单"
  ]
}
```

子工具可通过命令行参数 `--data=case-data.json` 读取数据。

## 手动配置工具路径

如果工具文件命名不符合预期，可以在 `config.json` 中手动指定路径：

```json
{
  "tools": {
    "reportStandard": "D:/工具/报告标准化工具.exe",
    "reportGenerate": "D:/工具/报告生成.exe",
    "mdToDocx": "D:/工具/附件md转docx工具.exe",
    "approvalForm": "D:/工具/结案审批表工具.exe",
    "catalogTool": "D:/工具/目录工具.exe"
  }
}
```

## 截图预览

界面采用现代化设计，支持：
- 案件信息录入与保存
- 工具选择与批量执行
- 实时进度显示
- 操作日志查看

# Remote Artifact Service

面向 Linux / ARM64 嵌入式设备的轻量级只读 HTTP Artifact Server。统一浏览远程设备上经配置授权的项目文件、实验报告和多媒体产物；服务只部署在嵌入式设备侧，通过 SSH Tunnel 从开发工作站访问。

## 设计原则

- **设备侧部署**：NX、RK3588、RDK S100、Orin NX 等目标设备各自运行服务；不在 PC1、LAP1 或 DSH Host 部署服务实例。
- **单一数据源**：文件始终留在设备原始目录，不建立本地项目副本，不做文件同步。
- **只读**：HTTP API 不提供上传、写入、重命名或删除接口。
- **默认回环监听**：默认绑定 127.0.0.1，通过 SSH Tunnel 访问。
- **路径围栏**：只允许读取配置的 root；解析符号链接后再次验证路径边界，阻止目录穿越和 symlink escape。
- **流式读取**：大文件按需传输，支持 HTTP Range，避免一次性加载到内存。
- **低维护**：Python 3.10+，ARM64/Linux，默认不依赖 Docker、数据库或外部 CDN。

## 第一版能力

- 多个只读目录 root 配置和目录浏览
- 文本、Markdown 源文、JSON、CSV、日志预览（v0.1 不做 Markdown 渲染）
- HTML 沙箱预览
- PNG/JPEG/GIF/WebP/SVG 图片预览
- MP4/WebM 视频、音频和 PDF 预览
- 文件下载与 HTTP Range（包括视频/音频预览所需的 Range 请求）
- 简单 Web UI、健康检查 API
- 配置文件、安装/启动/停止脚本
- 路径穿越、符号链接越界和只读行为测试

## 安装

要求 Python 3.10+。

```bash
git clone https://github.com/stillstream/remote-artifact-service.git
cd remote-artifact-service
bash scripts/install.sh
cp config/example.json config/config.json
```

编辑 config/config.json，只添加需要浏览的项目报告目录。不要配置整个 home、系统根目录、SSH 配置、密钥或凭据目录。

示例：

```json
{
  "host": "127.0.0.1",
  "port": 18765,
  "roots": [
    {
      "id": "uav-projects",
      "label": "UAV Projects",
      "path": "/home/nx/workspace/project",
      "show_hidden": false
    }
  ]
}
```

## 启动

```bash
bash scripts/start.sh
```

默认监听远端 127.0.0.1:18765。日志和 PID 放在用户级运行目录；停止：

```bash
bash scripts/stop.sh
```

也可直接运行：

```bash
.venv/bin/python -m artifact_service --config config/config.json
```

## 通过 SSH Tunnel 访问

在运行浏览器的 PC1 / LAP1 上执行：

```bash
ssh -N -L 18765:127.0.0.1:18765 <ssh-host-alias>
```

浏览器打开 http://127.0.0.1:18765/ 。SSH 别名应复用现有 ~/.ssh/config（含 ProxyJump / Tailscale 等配置）。隧道关闭后，本地链接自然不可用。

不要为了方便浏览把服务改为 0.0.0.0。若确有局域网直连需求，应另行设计认证和访问控制，不属于第一版。

## API

- GET /api/health：健康状态
- GET /api/roots：已配置 root 列表
- GET /api/entries?root_id=<id>&path=<relative-path>：列出目录项
- GET /api/file?root_id=<id>&path=<relative-path>：内联预览/流式读取，支持 Range
- GET /api/download?root_id=<id>&path=<relative-path>：附件下载

所有路径都相对于已配置 root。隐藏文件默认不显示；配置可按 root 开启。路径访问会进行 root 边界检查。服务不支持任何文件写入 API。

## 开发验证

```bash
python -m pip install -e '.[dev]'
pytest -q
```

## 当前状态

初始项目骨架。先在开发环境完成单元测试，再在 NX 上验证 ARM64 安装、目录访问、HTML/图片/视频预览和大文件 Range；未经验证不宣称已完成嵌入式部署。

## License

MIT

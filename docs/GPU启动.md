# Windows 自动独显启动

双击仓库根目录 `Start-PetIsland.cmd`。首次运行会创建桌面 **派特岛（自动独显）** 快捷方式；以后使用该快捷方式即可。服务未启动时自动启动 127.0.0.1:5002，已启动则复用。

启动器通过 DXGI 每次重新枚举硬件显卡，过滤软件适配器，按专用显存容量选择高性能适配器，传给 Chrome 当前 LUID。该选择是显存容量启发式，并非所有机器的性能排名；实际设备以页面「更多 → 流畅度」为准。

旧诊断脚本把 `0,98102` 固定写进命令，重启后该 LUID 可能失效。本次机器实际值已变成 `0,96749`。新脚本不保存或硬编码 LUID，修正高性能参数为 Chromium 的 `--force_high_performance_gpu`。

继续使用 `%LOCALAPPDATA%\PetChatSystem\ChromeGpuDiagnostic` 专用资料目录，保留之前登录、麦克风许可和站点状态。普通 Chrome 与内置浏览器是独立进程，点击普通网址不能保证进入专用窗口。启动器不关闭普通 Chrome，不开放调试端口、不关闭浏览器沙箱、不跳过驱动安全规则。若已打开的专用实例使用不同显卡参数，提示关闭那个窗口后重新打开，不强杀进程。

诊断（只读，不启动浏览器、不改注册表）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-island.ps1 -Inspect
```

运行记录在 `%LOCALAPPDATA%\PetChatSystem\last-gpu-launch.json`；自动启动服务的日志在同目录 `service.out.log`、`service.err.log`。Python 优先使用项目虚拟环境，其次本机 qijin666 环境，最后 PATH 上的 python；需要已安装项目依赖。

验证：服务启动后运行 `python test/gpu_launcher.py`。它用独立临时资料目录启动真实 Chrome，核对浏览器 GPU 和实际小岛 WebGL 上下文，结束时只关闭测试实例。临时调试端口仅用于这项测试，不进入正式启动参数。

接口参考：[Microsoft DXGI 枚举](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/nf-dxgi-idxgifactory1-enumadapters1)、[适配器描述](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/ns-dxgi-dxgi_adapter_desc1)、[Chromium 显卡选择参数](https://chromium.googlesource.com/chromium/src/+/81cac896e48f577529e31d055789f1b1f06cfe4a/ui/gl/gl_switches.cc)。

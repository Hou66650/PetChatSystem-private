from mermaid import mermaid

mermaid_code = """
graph LR
    classDef startend fill:#F5EBFF,stroke:#BE8FED,stroke-width:2px
    classDef process fill:#E5F6FF,stroke:#73A6FF,stroke-width:2px
    classDef decision fill:#FFF6CC,stroke:#FFBC52,stroke-width:2px

    A([开始]):::startend --> B(用户访问系统):::process
    B --> C{选择操作}:::decision
    C -->|登录| D(输入用户名和密码):::process
    D --> E[/调用 /login 接口/]:::process
    E --> F{验证是否通过}:::decision
    F -->|是| G(登录成功，获取 token):::process
    F -->|否| D
    C -->|注册| H(填写注册信息):::process
    H --> I[/调用 /register 接口/]:::process
    I --> J(注册成功):::process
    G --> K(进入主聊天页面 - gpt_me.html):::process
    K --> L(输入消息):::process
    L --> M[/调用 /get_gpt_response 接口/]:::process
    M --> N(显示 AI 助手回复):::process
    K --> O{选择其他操作}:::decision
    O -->|上传头像| P(选择头像图片):::process
    P --> Q[/调用 /upload-avatar 接口/]:::process
    Q --> R(更新用户头像):::process
    R --> S[/调用 gpt - image - 1 模型生成动漫头像/]:::process
    S --> T(更新用户资料为动漫头像):::process
    O -->|查看宠物反馈| U[/调用 /remark_pet 接口/]:::process
    U --> V(跳转到宠物反馈页面 - remark_pet.html):::process
    O -->|查看日记本| W[/调用 /diary 接口/]:::process
    W --> X(跳转到日记本页面 - diary.html):::process
    O -->|返回入口页面| Y[/调用 /reader 接口/]:::process
    Y --> Z(回到系统起始页面 - index.html):::process
    K --> AA(保存聊天记录为 PDF):::process
    AA --> BB[/Marked.js 解析 Markdown/]:::process
    BB --> CC[/html2canvas 转换 HTML 为图像/]:::process
    CC --> DD[/jsPDF 生成 PDF 文件/]:::process

    B --> EE(访问登录页面 - login.html):::process
    B --> FF(访问注册页面 - register.html):::process
    B --> GG(访问管理员注册页面 - register_admin.html):::process
    B --> HH(访问管理员登录页面 - manager_login.html):::process
    EE --> E
    FF --> I
    GG --> II[/调用 /register_admin 接口/]:::process
    II --> JJ(管理员注册成功):::process
    HH --> KK[/调用 /manager_login 接口/]:::process
    KK --> LL{管理员验证是否通过}:::decision
    LL -->|是| MM(管理员登录成功，进入管理页面 - manager.html):::process
    LL -->|否| HH

    O --> NN(跳转到用户信息页面 - user_info.html):::process
    O --> OO(跳转到关于我们页面 - about_us.html):::process
"""

mermaid(mermaid_code)

# -*- coding: utf-8 -*-
"""页面对象包（Page Object Model）。

每个模块一个文件，类与页面一一对应：

- login_page.py       登录页
- layout_page.py      登录后的全局框架（菜单 / 用户下拉），被其他模块组合使用
- password_modal.py   修改密码弹窗（组件对象）
- database_page.py    专病检索（专病库列表 + 专病库详情 + 查询统计弹窗）
- chat_page.py        灵犀问答（会话列表 + 对话区）
- annotation_page.py  智能标注（标注任务列表 + 任务详情）
"""

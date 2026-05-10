# Review Site Publishing

这份说明对应当前仓库里的静态审阅网站，目标是把它整理成适合提交到 GitHub、再通过 GitHub Pages 给团队共享的版本。

## 为什么不能直接发布旧版本

旧版站点有两个问题：

- `data/site_bundle.json` 是单文件大包，体积超过 `100 MB`
- `assets/boards` 默认是本地符号链接，离开当前机器就会失效

发布版已经改成：

- `data/summary.json`
- `data/experiments.json`
- `data/games_manifest.json`
- `data/games/<game_id>.json`
- `assets/boards/*.png`

也就是说：

- 数据按对局分片
- 图片是真实拷贝
- 可以直接作为静态站托管

## 一键构建发布版

在仓库根目录运行：

```bash
bash scripts/review/build_publishable_review_site.sh
```

默认会生成到：

```bash
publish/review-site-github-pages/site
```

如果你想改输出目录：

```bash
bash scripts/review/build_publishable_review_site.sh publish/my-team-review-site
```

## 本地预览

```bash
python3 -m http.server 8765 -d publish/review-site-github-pages/site
```

然后打开：

```text
http://127.0.0.1:8765
```

## 推荐的 GitHub 协作方式

### 代码协作

把整个项目仓库推到 GitHub，这样同事可以：

- 看分析代码
- 改网站前端
- 改实验脚本
- 提 PR

### 网站共享

推荐把下面这个目录作为 GitHub Pages 的发布源：

```text
publish/review-site-github-pages/site
```

当前仓库已经放了一个 GitHub Actions workflow：

```text
.github/workflows/publish-review-site.yml
```

它会把这个静态目录发布到 GitHub Pages。

## GitHub 上的最短流程

1. 新建 GitHub 仓库
2. 把当前项目 push 上去
3. 在 GitHub 仓库设置里打开 `Pages`
4. 允许 Actions 部署 Pages
5. 提交一次发布版站点
6. 等 workflow 跑完

之后同事就可以通过一个固定 URL 看站点。

## 更新网站的方式

每次你重新跑完实验后：

1. 更新实验输出
2. 重新运行：

```bash
bash scripts/review/build_publishable_review_site.sh
```

3. 提交新的 `publish/review-site-github-pages/site`
4. push 到 GitHub
5. Pages 会自动更新

## 注意事项

- 发布版仍然会比较大，因为包含棋盘 PNG 和按对局拆分后的 JSON
- 但它已经规避了 GitHub 单文件 `100 MB` 限制
- 如果以后扩到 `1000` 局或 `10000` 局，建议继续细分：
  - 按 Elo 段拆 manifest
  - 按实验拆单独 JSON
  - 图片按需单独目录发布

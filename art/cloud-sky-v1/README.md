# 空岛云海背景 v1

2026-10-14，使用内置 image_gen，先生成原画后接入网页。未使用 CLI 或外部素材。

- day.png / night.png：生成原画，1672 × 941；夜景以日景为编辑参考，保持云层构图。
- 网页资源：static/textures/cloud-sky-v1/day.webp、night.webp，原尺寸 WebP quality=90。无内容修改。
- 昼夜随现有系统切换。/den?scene=day 与 /den?scene=night 可分别验收，morning/dusk 使用暖色日间画。
- Three.js 二维背景贴图，居中 cover 裁切，不参与碰撞与移动，不是环境光 HDRI。竖屏优先保留画面中心，月亮可能裁到画面外。

## 生成提示

日景：Create a finished production background texture for a cozy stylized 3D virtual pet game, landscape 16:9. SKY AND DISTANT CLOUD ENVIRONMENT ONLY, behind an existing floating circular cream-green island, pink cherry tree and orange shiba. Do not draw island, ground, pets, trees, furniture, UI or text. Airy storybook / soft clay animated-film matte painting. Pale cornflower blue upper sky grading through periwinkle to warm peach-pink and cream at a low horizon. Sunlit sculptural clouds frame left and right edges, distant lavender-blue cloud banks and luminous cloud sea across the lower third. Central 55 percent open and low contrast, top middle unobstructed. Asymmetrical cloud shapes, glowing edges, depth and haze. Balanced pastel, no neon, no storm, no borders, no lettering, no collage. Full-bleed production artwork.

夜景编辑：Preserve exact wide composition, cloud sea, open central space, cloud silhouettes and painted sculptural style. Change to inviting moonlit blue-hour: rich muted indigo and periwinkle upper sky, silver-lavender cloud edges, dusty-rose to blue-violet low horizon. Remove horizon sun. Small warm-ivory crescent at x78%, y19%, subtle halo, sparse varied tiny stars, no dense galaxy. Central 55 percent stays quiet. No ground, islands, trees, pets, buildings, UI, text or collage. Calm bedtime, no neon, no aurora.

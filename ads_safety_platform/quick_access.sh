#!/bin/bash
# ADS Safety Platform - 快速访问脚本

echo "=========================================="
echo "ADS Safety Platform - 快速访问菜单"
echo "=========================================="
echo ""

PS3="请选择操作: "
options=(
    "在浏览器中打开HTML演示页面"
    "复制HTML文件到桌面"
    "查看文件信息"
    "查看GitHub仓库"
    "退出"
)

select opt in "${options[@]}"; do
    case $opt in
        "在浏览器中打开HTML演示页面")
            echo "正在打开 HTML 演示页面..."
            xdg-open /home/aisecurity/01_ZHB/ads_safety_platform/index.html
            ;;
        "复制HTML文件到桌面")
            echo "正在复制文件到桌面..."
            cp /home/aisecurity/01_ZHB/ads_safety_platform/index.html ~/Desktop/
            echo "✅ 文件已复制到: ~/Desktop/index.html"
            ;;
        "查看文件信息")
            echo "文件信息:"
            ls -lh /home/aisecurity/01_ZHB/ads_safety_platform/index.html
            echo ""
            echo "文件大小: $(du -h /home/aisecurity/01_ZHB/ads_safety_platform/index.html | cut -f1)"
            echo "行数: $(wc -l < /home/aisecurity/01_ZHB/ads_safety_platform/index.html)"
            ;;
        "查看GitHub仓库")
            echo "正在打开 GitHub 仓库..."
            xdg-open https://github.com/small1zhang/ads_safety_platform
            ;;
        "退出")
            echo "再见！"
            exit 0
            ;;
        *) 
            echo "无效选项，请重新选择"
            ;;
    esac
    echo ""
done

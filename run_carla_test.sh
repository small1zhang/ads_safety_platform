#!/bin/bash
# 🚀 CARLA自动化检测启动脚本
# 
# 功能:
# 1. 检查并启动CARLA服务
# 2. 运行30分钟实时检测
# 3. 生成检测报告
# 4. 自动清理资源
#
# 使用方法:
#   chmod +x run_carla_test.sh
#   ./run_carla_test.sh [duration_minutes] [output_dir]
#
# 示例:
#   ./run_carla_test.sh 30 output_30min
#   ./run_carla_test.sh          # 默认30分钟

set -e

# ============================================================================
# 配置参数
# ============================================================================

# 默认参数
DURATION_MINUTES=${1:-30}
OUTPUT_DIR=${2:-output_$(date +%Y%m%d_%H%M%S)}
CARLA_HOST="localhost"
CARLA_PORT=2000
PYTHON_SCRIPT="backend/app/realtime_carla_collector.py"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# 函数定义
# ============================================================================

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查CARLA服务是否运行
check_carla_running() {
    if ps aux | grep -i carla | grep -v grep > /dev/null 2>&1; then
        return 0
    fi
    
    # 检查端口
    if netstat -tuln 2>/dev/null | grep "${CARLA_PORT}" > /dev/null; then
        return 0
    elif ss -tuln 2>/dev/null | grep "${CARLA_PORT}" > /dev/null; then
        return 0
    fi
    
    return 1
}

# 启动CARLA服务
start_carla() {
    print_info "尝试启动CARLA服务..."
    
    # 检查是否有CARLA安装
    if [ -d "/opt/carla-simulator" ]; then
        print_info "找到CARLA安装目录: /opt/carla-simulator"
        cd /opt/carla-simulator
        nohup ./CarlaUE4.sh -RenderOffScreen > /tmp/carla.log 2>&1 &
        sleep 10
        
        if check_carla_running; then
            print_success "CARLA服务启动成功"
            return 0
        else
            print_error "CARLA服务启动失败"
            print_info "查看日志: tail -f /tmp/carla.log"
            return 1
        fi
    fi
    
    # 检查Docker
    if command -v docker > /dev/null 2>&1; then
        print_info "尝试使用Docker启动CARLA..."
        docker run -d --rm --name carla-server \
            -p 2000-2002:2000-2002 \
            --gpus all \
            carlasim/carla:0.9.14 \
            /bin/bash -c "SDL_VIDEODRIVER=offscreen /opt/carla-simulator/CarlaUE4.sh -RenderOffScreen"
        
        sleep 15
        
        if check_carla_running; then
            print_success "CARLA Docker容器启动成功"
            return 0
        else
            print_error "CARLA Docker容器启动失败"
            docker logs carla-server 2>&1 | tail -20
            return 1
        fi
    fi
    
    print_error "无法找到CARLA安装或Docker"
    return 1
}

# 停止CARLA服务
stop_carla() {
    print_info "停止CARLA服务..."
    
    # 停止本地CARLA进程
    pkill -f "CarlaUE4" 2>/dev/null || true
    pkill -f "carla" 2>/dev/null || true
    
    # 停止Docker容器
    docker stop carla-server 2>/dev/null || true
    docker rm carla-server 2>/dev/null || true
    
    print_success "CARLA服务已停止"
}

# 运行检测
run_detection() {
    local duration_seconds=$((DURATION_MINUTES * 60))
    
    print_info "开始运行 ${DURATION_MINUTES} 分钟实时检测..."
    print_info "检测时长: ${duration_seconds} 秒"
    print_info "输出目录: ${OUTPUT_DIR}"
    
    # 创建输出目录
    mkdir -p "${OUTPUT_DIR}"
    
    # 运行检测脚本
    python3 "${PYTHON_SCRIPT}" \
        --duration "${duration_seconds}" \
        --interval 2.0 \
        --inject-anomalies true \
        --output-dir "${OUTPUT_DIR}" \
        2>&1 | tee "${OUTPUT_DIR}/detection.log"
    
    print_success "检测完成！"
}

# 生成报告
generate_report() {
    print_info "生成检测报告..."
    
    local report_file="${OUTPUT_DIR}/REPORT.md"
    
    cat > "${report_file}" << EOF
# 📊 CARLA实时检测报告

## 基本信息
- **检测开始时间**: $(date -d "@$(stat -c %Y ${OUTPUT_DIR}/detection.log 2>/dev/null || echo $(date +%s))")
- **检测结束时间**: $(date)
- **检测时长**: ${DURATION_MINUTES} 分钟
- **输出目录**: ${OUTPUT_DIR}

## 检测统计
EOF
    
    # 尝试从日志中提取统计信息
    if [ -f "${OUTPUT_DIR}/detection.log" ]; then
        local total_scenarios=$(grep -oP '总场景数: \K[0-9]+' "${OUTPUT_DIR}/detection.log" || echo "N/A")
        local total_anomalies=$(grep -oP '总异常数: \K[0-9]+' "${OUTPUT_DIR}/detection.log" || echo "N/A")
        local detection_rate=$(grep -oP '检出率: \K[0-9.]+%' "${OUTPUT_DIR}/detection.log" || echo "N/A")
        
        cat >> "${report_file}" << EOF
- **总场景数**: ${total_scenarios}
- **总异常数**: ${total_anomalies}
- **检出率**: ${detection_rate}

## 风险分布
EOF
        
        # 提取风险分布
        grep -oP 'CRITICAL.*\K[0-9]+' "${OUTPUT_DIR}/detection.log" 2>/dev/null && echo "- CRITICAL: N/A" >> "${report_file}"
        grep -oP 'HIGH.*\K[0-9]+' "${OUTPUT_DIR}/detection.log" 2>/dev/null && echo "- HIGH: N/A" >> "${report_file}"
        grep -oP 'MEDIUM.*\K[0-9]+' "${OUTPUT_DIR}/detection.log" 2>/dev/null && echo "- MEDIUM: N/A" >> "${report_file}"
        grep -oP 'LOW.*\K[0-9]+' "${OUTPUT_DIR}/detection.log" 2>/dev/null && echo "- LOW: N/A" >> "${report_file}"
    fi
    
    cat >> "${report_file}" << EOF

## 输出文件
- [检测日志](detection.log)
- [异常列表](anomalies/)
- [知识图谱](html/)

## 总结
检测已成功完成，详细结果请查看相关文件。

---
*报告生成时间: $(date)*
EOF
    
    print_success "报告已生成: ${report_file}"
}

# 显示检测结果
show_results() {
    print_info ""
    print_info "=========================================="
    print_info "         检测结果总览"
    print_info "=========================================="
    
    if [ -f "${OUTPUT_DIR}/detection.log" ]; then
        echo ""
        print_info "检测日志位置: ${OUTPUT_DIR}/detection.log"
        
        # 显示最后20行日志
        print_info "最后20行日志:"
        tail -20 "${OUTPUT_DIR}/detection.log"
        
        echo ""
        print_info "输出文件:"
        ls -lh "${OUTPUT_DIR}" | grep -v "^d" | tail -10
        
        if [ -d "${OUTPUT_DIR}/anomalies" ]; then
            local anomaly_count=$(ls "${OUTPUT_DIR}/anomalies" 2>/dev/null | wc -l)
            print_info "异常文件数量: ${anomaly_count}"
        fi
        
        if [ -d "${OUTPUT_DIR}/html" ]; then
            local html_count=$(ls "${OUTPUT_DIR}/html" 2>/dev/null | wc -l)
            print_info "HTML文件数量: ${html_count}"
        fi
    else
        print_warning "未找到检测日志文件"
    fi
    
    print_info "=========================================="
}

# ============================================================================
# 主程序
# ============================================================================

# 显示欢迎信息
print_info "=========================================="
print_info "   CARLA自动化检测启动脚本"
print_info "=========================================="
print_info "检测时长: ${DURATION_MINUTES} 分钟"
print_info "输出目录: ${OUTPUT_DIR}"
print_info ""

# 检查CARLA服务
print_info "检查CARLA服务状态..."
if check_carla_running; then
    print_success "CARLA服务已在运行"
else
    print_warning "CARLA服务未运行"
    read -p "是否尝试自动启动CARLA? (y/n) [n]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if ! start_carla; then
            print_error "CARLA服务启动失败，将使用模拟数据模式"
            read -p "继续使用模拟数据模式? (y/n) [y]: " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                print_info "使用模拟数据模式运行检测..."
            else
                print_error "取消检测"
                exit 1
            fi
        fi
    else
        print_info "使用模拟数据模式运行检测..."
    fi
fi

# 运行检测
print_info ""
run_detection

# 生成报告
generate_report

# 显示结果
show_results

# 显示完成信息
print_info ""
print_success "=========================================="
print_success "   ✅ CARLA检测完成！"
print_success "=========================================="
print_info ""
print_info "检测结果已保存到: ${OUTPUT_DIR}/"
print_info "详细报告: ${OUTPUT_DIR}/REPORT.md"
print_info ""
print_info "您可以使用以下命令查看结果:"
print_info "  cd ${OUTPUT_DIR}"
print_info "  ls -la"
print_info "  cat REPORT.md"
print_info ""

# 可选：停止CARLA服务
read -p "是否停止CARLA服务? (y/n) [n]: " -n 1 -r
if [[ $REPLY =~ ^[Yy]$ ]]; then
    stop_carla
fi

exit 0
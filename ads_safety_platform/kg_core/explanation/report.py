"""
可解释性安全报告生成器
为每个风险判定生成自然语言解释
"""
from typing import Dict, Any, List, Optional
from datetime import datetime


class ExplanationGenerator:
    """可解释性报告生成器"""
    
    RISK_LEVEL_MAP = {
        0: "SAFE",
        1: "UNCERTAIN",
        2: "UNSAFE",
    }
    
    def __init__(self):
        self.risk_level_map = self.RISK_LEVEL_MAP
    
    def generate_report(self, 
                       snapshot: Dict[str, Any],
                       violations: List[Dict[str, Any]],
                       frame_id: int,
                       timestamp: float = None) -> Dict[str, Any]:
        """
        生成可解释性安全报告
        
        参数:
            snapshot: 场景快照数据
            violations: 违规列表
            frame_id: 帧 ID
            timestamp: 时间戳
        
        返回:
            完整的解释性报告
        """
        if timestamp is None:
            timestamp = datetime.now().timestamp()
        
        # 确定整体风险等级
        risk_level = self._compute_risk_level(violations)
        
        # 生成自然语言解释
        natural_language = self._generate_natural_language(
            snapshot, violations, frame_id
        )
        
        # 构建证据链
        evidence_chain = self._build_evidence_chain(snapshot, violations)
        
        # 构建风险摘要
        risk_summary = self._build_risk_summary(violations, frame_id)
        
        report = {
            'frame_id': frame_id,
            'timestamp': timestamp,
            'risk_level': risk_level,
            'risk_level_str': self.risk_level_map.get(risk_level, 'UNKNOWN'),
            'natural_language': natural_language,
            'violations': violations,
            'evidence_chain': evidence_chain,
            'risk_summary': risk_summary,
        }
        
        return report
    
    def _compute_risk_level(self, violations: List[Dict[str, Any]]) -> int:
        """计算整体风险等级"""
        if not violations:
            return 0  # SAFE
        
        # 检查是否有 CRITICAL 严重程度
        for v in violations:
            if v.get('severity') == 'CRITICAL':
                return 2  # UNSAFE
        
        # 检查是否有 HIGH 严重程度
        for v in violations:
            if v.get('severity') == 'HIGH':
                return 2  # UNSAFE
        
        return 1  # UNCERTAIN
    
    def _generate_natural_language(self,
                                   snapshot: Dict[str, Any],
                                   violations: List[Dict[str, Any]],
                                   frame_id: int) -> str:
        """生成自然语言描述"""
        if not violations:
            return "检测到无风险情况，驾驶行为规范。"
        
        lines = []
        lines.append(f"检测到 {len(violations)} 个安全问题：")
        
        for i, v in enumerate(violations, 1):
            rule_code = v.get('rule_code', '未知规则')
            severity = v.get('severity', 'UNKNOWN')
            message = v.get('message', '无描述')
            
            # 根据规则类型组织语言
            if 'RSS' in rule_code:
                lines.append(f"{i}. {message}（规则: {rule_code}）")
            elif 'R2' in rule_code or 'RED_LIGHT' in rule_code:
                lines.append(f"{i}. 闯红灯风险：{message}（规则: {rule_code}）")
            elif 'COLLISION' in rule_code:
                lines.append(f"{i}. 碰撞风险：{message}（规则: {rule_code}）")
            else:
                lines.append(f"{i}. {message}（规则: {rule_code}）")
        
        return "\n".join(lines)
    
    def _build_evidence_chain(self, 
                              snapshot: Dict[str, Any],
                              violations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """构建证据链"""
        evidence_chain = {
            'scene_evidence': [],
            'physics_evidence': [],
            'rule_evidence': [],
        }
        
        # 场景证据
        vehicles = snapshot.get('vehicles', [])
        for v in vehicles:
            evidence_chain['scene_evidence'].append({
                'type': 'Vehicle',
                'entity_id': v.get('entity_id'),
                'position': {'x': v.get('x'), 'y': v.get('y'), 'z': v.get('z')},
                'speed': v.get('speed'),
            })
        
        # 交通灯证据
        traffic_lights = snapshot.get('traffic_lights', [])
        for tl in traffic_lights:
            evidence_chain['rule_evidence'].append({
                'type': 'TrafficLight',
                'entity_id': tl.get('entity_id'),
                'state': tl.get('state'),
                'position': {'x': tl.get('x'), 'y': tl.get('y'), 'z': tl.get('z')},
            })
        
        # 违规证据
        for v in violations:
            evidence_chain['rule_evidence'].append({
                'type': 'Violation',
                'rule_code': v.get('rule_code'),
                'message': v.get('message'),
            })
        
        return evidence_chain
    
    def _build_risk_summary(self, 
                           violations: List[Dict[str, Any]],
                           frame_id: int) -> Dict[str, Any]:
        """构建风险摘要"""
        risk_counts = {}
        severity_counts = {}
        
        for v in violations:
            rule_code = v.get('rule_code', 'unknown')
            severity = v.get('severity', 'UNKNOWN')
            
            risk_counts[rule_code] = risk_counts.get(rule_code, 0) + 1
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            'total_violations': len(violations),
            'by_rule': risk_counts,
            'by_severity': severity_counts,
            'frame_id': frame_id,
        }
    
    def format_report_as_markdown(self, report: Dict[str, Any]) -> str:
        """将报告格式化为 Markdown 文本"""
        lines = []
        lines.append("# 自动驾驶安全风险报告")
        lines.append("")
        lines.append(f"**帧ID**: {report['frame_id']}")
        lines.append(f"**生成时间**: {report['timestamp']}")
        lines.append(f"**风险等级**: {report['risk_level_str']}")
        lines.append("")
        lines.append("## 自然语言描述")
        lines.append(report['natural_language'])
        lines.append("")
        lines.append("## 风险摘要")
        
        summary = report['risk_summary']
        lines.append(f"- 总违规数: {summary['total_violations']}")
        lines.append(f"- 严重程度分布: {summary['by_severity']}")
        
        lines.append("")
        lines.append("## 详细违规")
        for v in report['violations']:
            lines.append(f"### {v.get('rule_code', '未知')} ({v.get('severity', 'UNKNOWN')})")
            lines.append(f"- 描述: {v.get('message', '无')}")
            lines.append(f"- 证据: {v.get('evidence', {})}")
            lines.append("")
        
        return "\n".join(lines)
"""
paths.py - 项目路径配置
统一管理项目所有输出路径，避免硬编码
"""

from pathlib import Path


class ProjectPaths:
    """项目路径管理器"""
    
    def __init__(self, project_root: str = None):
        if project_root is None:
            # 自动检测项目根目录（向上查找含src的目录）
            current = Path(__file__).resolve()
            for parent in [current] + list(current.parents):
                if (parent / 'src').exists():
                    project_root = parent
                    break
            else:
                project_root = current.parent
        
        self.project_root = Path(project_root)
        self.src_dir = self.project_root / 'src'
        self.tests_dir = self.project_root / 'tests'
        self.results_dir = self.project_root / 'results'
        self.output_dir = self.project_root / 'output'
        self.configs_dir = self.project_root / 'configs'
        self.docs_dir = self.project_root / 'docs'
        
        # 结果子目录
        self.kg_output_dir = self.results_dir / 'kg_output'
        self.reports_dir = self.results_dir / 'reports'
        self.anomalies_dir = self.results_dir / 'anomalies'
        
        # 输出子目录
        self.html_output_dir = self.output_dir / 'html'
        self.json_output_dir = self.output_dir / 'json'
        
        # 确保所有目录存在
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """确保所有目录存在"""
        for dir_path in [self.results_dir, self.output_dir,
                        self.kg_output_dir, self.reports_dir, self.anomalies_dir,
                        self.html_output_dir, self.json_output_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    @property
    def visualization_demo(self) -> Path:
        """可视化页面路径"""
        return self.html_output_dir / 'visualization_demo.html'
    
    @property
    def knowledge_graph_latest(self) -> Path:
        """最新的知识图谱HTML"""
        return self.html_output_dir / 'knowledge_graph_latest.html'
    
    @property
    def index_html(self) -> Path:
        """主入口HTML"""
        return self.html_output_dir / 'index.html'
    
    def get_anomaly_path(self, anomaly_id: int, timestamp: str) -> Path:
        """获取异常详情页面路径"""
        ts = timestamp.replace(':', '-')[:14]
        return self.anomalies_dir / f'anomaly_{anomaly_id:03d}_{ts}.html'
    
    def get_kg_path(self, timestamp: str) -> Path:
        """获取知识图谱页面路径（带时间戳）"""
        ts = timestamp.replace(':', '-').replace('-', '')[:14]
        return self.html_output_dir / f'knowledge_graph_{ts}.html'


# 全局实例
PATHS = ProjectPaths()
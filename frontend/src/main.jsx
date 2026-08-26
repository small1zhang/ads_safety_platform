import React from 'react'
import ReactDOM from 'react-dom/client'
import { useState, useEffect } from 'react'
import { Button, Statistic, Row, Col, Card, Typography, Spin } from 'antd'
import axios from 'axios'

const { Title, Text } = Typography

// API 地址 - 使用相对路径
const apiUrl = '/api'

function App() {
    const [health, setHealth] = useState(null)
    const [stats, setStats] = useState(null)
    const [loading, setLoading] = useState(true)
    const [knowledgeGraph, setKnowledgeGraph] = useState(null)

    useEffect(() => {
        fetchHealth()
        fetchStats()
        fetchKG()

        const interval = setInterval(() => {
            fetchStats()
        }, 5000)

        return () => clearInterval(interval)
    }, [])

    const fetchHealth = async () => {
        try {
            const response = await axios.get(`${apiUrl}/health`)
            setHealth(response.data)
        } catch (error) {
            console.error('Health check failed:', error)
        }
    }

    const fetchStats = async () => {
        try {
            const response = await axios.get(`${apiUrl}/detect/history`)
            setStats(response.data)
            setLoading(false)
        } catch (error) {
            console.error('Stats fetch failed:', error)
            setLoading(false)
        }
    }

    const fetchKG = async () => {
        try {
            const response = await axios.get(`${apiUrl}/kg/latest`)
            setKnowledgeGraph(response.data)
        } catch (error) {
            console.log('No KG data yet')
        }
    }

    const runDetection = async (duration = 10) => {
        try {
            const response = await axios.post(`${apiUrl}/detect/run`, {
                duration: duration,
                interval: 1.0,
                inject_anomalies: true
            })
            setStats(response.data)
        } catch (error) {
            console.error('Detection failed:', error)
        }
    }

    const generateKG = async () => {
        try {
            await axios.get(`${apiUrl}/kg/generate`)
            fetchKG()
        } catch (error) {
            console.error('KG generation failed:', error)
        }
    }

    if (loading) {
        return (
            <div style={{ textAlign: 'center', marginTop: 50 }}>
                <Spin size="large" />
                <Text style={{ display: 'block', marginTop: 20 }}>加载中...</Text>
            </div>
        )
    }

    const total = stats?.stats?.total || 0
    const critical = stats?.stats?.critical || 0
    const high = stats?.stats?.high || 0
    const medium = stats?.stats?.medium || 0
    const low = stats?.stats?.low || 0

    return (
        <div style={{ padding: 20 }}>
            <div className="header">
                <Title level={1}>🚗 ADS Safety Platform</Title>
                <Title level={3}>实时异常检测仪表盘</Title>
                <Text>状态: {health?.status === 'healthy' ? '🟢 在线' : '🔴 离线'} | 总时长: {total > 0 ? '检测中' : '就绪'}</Text>
            </div>

            <div className="stats-bar">
                <div className="stat-item">
                    <div className="stat-value">{total}</div>
                    <div className="stat-label">总异常数</div>
                </div>
                <div className="stat-item">
                    <div className="stat-value" style={{ color: '#e74c3c' }}>{critical}</div>
                    <div className="stat-label">危急</div>
                </div>
                <div className="stat-item">
                    <div className="stat-value" style={{ color: '#e67e22' }}>{high}</div>
                    <div className="stat-label">高危</div>
                </div>
                <div className="stat-item">
                    <div className="stat-value" style={{ color: '#f39c12' }}>{medium}</div>
                    <div className="stat-label">中危</div>
                </div>
                <div className="stat-item">
                    <div className="stat-value" style={{ color: '#2ecc71' }}>{low}</div>
                    <div className="stat-label">低危</div>
                </div>
            </div>

            <div style={{ marginBottom: 20 }}>
                <Button className="btn btn-primary" onClick={() => runDetection(10)}>
                    运行10秒检测
                </Button>
                <Button className="btn btn-success" onClick={() => runDetection(60)}>
                    运行1分钟检测
                </Button>
                <Button className="btn-warning" onClick={generateKG}>
                    生成知识图谱
                </Button>
            </div>

            <Button className="kg-btn" onClick={() => window.open('/knowledge_graph.html', '_blank')}>
                📊 查看知识图谱
            </Button>

            <div style={{ marginTop: 30 }}>
                <Title level={3}>📋 最近检测结果</Title>
                <div className="card-grid">
                    {stats?.results?.slice(0, 6).map((r, i) => (
                        <Card key={i} className="card" hoverable>
                            <Title level={5}>{r.scenario_name}</Title>
                            <Text type="secondary">{new Date(r.timestamp).toLocaleString()}</Text>
                            <br />
                            <span className={`risk-badge ${r.risk_level.toLowerCase()}`}>
                                {r.risk_level} ({r.risk_index})
                            </span>
                            <br />
                            <Text type="secondary">速度: {r.ego_speed.toFixed(1)} m/s</Text>
                            <br />
                            <Text type="secondary">车辆: {r.vehicle_count}</Text>
                            <br />
                            <Text type="secondary">违规: {r.violations?.length || 0} 项</Text>
                        </Card>
                    ))}
                </div>
            </div>
        </div>
    )
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />)

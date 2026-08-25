import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import {
  HomeOutlined,
  BarChartOutlined,
  ExperimentOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import Dashboard from './components/Dashboard'
import KnowledgeGraph from './components/KnowledgeGraph'
import AnomalyManagement from './components/AnomalyManagement'
import Settings from './components/Settings'

const { Header, Content, Sider } = Layout

function App() {
  return (
    <BrowserRouter>
      <Layout style={{ minHeight: '100vh' }}>
        <Sider>
          <div style={{ color: '#fff', padding: '1rem', fontSize: '1.25rem', fontWeight: 'bold' }}>
            ADS Safety Platform
          </div>
          <Menu theme="dark" mode="menu" defaultSelectedKeys={['dashboard']}>
            <Menu.Item key="dashboard" icon={<HomeOutlined />}>
              <a href="/dashboard">仪表盘</a>
            </Menu.Item>
            <Menu.Item key="kg" icon={<BarChartOutlined />}>
              <a href="/knowledge-graph">知识图谱</a>
            </Menu.Item>
            <Menu.Item key="anomalies" icon={<ExperimentOutlined />}>
              <a href="/anomalies">异常管理</a>
            </Menu.Item>
            <Menu.Item key="settings" icon={<SettingOutlined />}>
              <a href="/settings">设置</a>
            </Menu.Item>
          </Menu>
        </Sider>
        <Layout>
          <Header style={{ background: '#fff', padding: '0 20px' }}>
            <h2>ADS Safety Platform - 实时异常检测</h2>
          </Header>
          <Content style={{ margin: '16px' }}>
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/knowledge-graph" element={<KnowledgeGraph />} />
              <Route path="/anomalies" element={<AnomalyManagement />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </Content>
        </Layout>
      </Layout>
    </BrowserRouter>
  )
}

export default App
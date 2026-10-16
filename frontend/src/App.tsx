import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import TopNav from './components/TopNav';
import Sidebar from './components/Sidebar';
import ShimmerBar from './components/ShimmerBar';
import ChatPage from './pages/Chat';
import KnowledgePage from './pages/KnowledgeBase';
import TaskCenterPage from './pages/TaskCenter';
import SettingsPage from './pages/Settings';

const App: React.FC = () => (
  <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
    {/* 顶部悬浮导航 */}
    <TopNav />

    {/* 主体三栏布局 */}
    <div style={{ display: 'flex', flex: 1, overflow: 'hidden', position: 'relative', zIndex: 1 }}>
      {/* 左侧磨砂玻璃侧边栏 */}
      <Sidebar />

      {/* 中间 + 右侧内容区 */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', padding: '16px 16px 6px 8px', gap: 12 }}>
        <Routes>
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
          <Route path="/tasks" element={<TaskCenterPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </div>
    </div>

    {/* 底部超细进度条 */}
    <ShimmerBar />
  </div>
);

export default App;

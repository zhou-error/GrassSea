import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Input, Typography, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { loginApi } from '../api';
import { useAuthStore } from '../stores/authStore';

const { Title, Text } = Typography;

const LoginPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const handleLogin = async () => {
    setLoading(true);
    try {
      const res = await loginApi(username, password);
      setAuth(res.data.token, res.data.user);
      message.success('登录成功');
      navigate('/chat');
    } catch {
      message.error('登录失败，请检查用户名和密码');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      minHeight: '100vh',
      background: 'linear-gradient(160deg, #F4F6F7 0%, #E8ECEE 40%, #EEF2F2 100%)',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* 背景波浪暗纹 */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none', opacity: 0.025,
        backgroundImage: `url("data:image/svg+xml,%3Csvg width='1200' height='800' viewBox='0 0 1200 800' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M0 500 Q200 420 400 500 Q600 580 800 500 Q1000 420 1200 500' fill='none' stroke='%23889999' stroke-width='0.5'/%3E%3C/svg%3E")`,
        backgroundSize: 'cover',
      }} />

      <div style={{
        width: 420, padding: '48px 40px',
        background: 'var(--glass-bg)',
        backdropFilter: 'blur(24px) saturate(140%)',
        borderRadius: 'var(--radius-xl)',
        boxShadow: '0 4px 32px rgba(0,0,0,0.06)',
        border: '1px solid var(--glass-border)',
        position: 'relative', zIndex: 1,
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <svg width="44" height="44" viewBox="0 0 44 44" fill="none" style={{ margin: '0 auto 16px' }}>
            <defs>
              <linearGradient id="loginLogo" x1="0" y1="0" x2="44" y2="44">
                <stop offset="0%" stopColor="#C1D5C0" />
                <stop offset="100%" stopColor="#B5D6E0" />
              </linearGradient>
            </defs>
            <path d="M6 34 Q12 16 22 10 Q32 16 38 34" stroke="url(#loginLogo)" strokeWidth="2.2" fill="none" strokeLinecap="round" />
            <path d="M10 28 Q14 18 22 14 Q30 18 34 28" stroke="url(#loginLogo)" strokeWidth="1.4" fill="none" strokeLinecap="round" opacity="0.5" />
            <circle cx="22" cy="22" r="2" fill="#C1D5C0" opacity="0.6" />
          </svg>
          <Title level={2} style={{ marginBottom: 4, fontWeight: 600, letterSpacing: '-0.02em' }}>
            GrassSea AI
          </Title>
          <Text type="secondary" style={{ fontSize: 13, letterSpacing: '0.03em' }}>
            白草沧智 · 船舶海洋工程智能平台
          </Text>
        </div>

        {/* 表单 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Input
            size="large"
            prefix={<UserOutlined style={{ color: 'var(--text-muted)' }} />}
            placeholder="用户名"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onPressEnter={handleLogin}
            style={{
              borderRadius: 'var(--radius-md)',
              border: '1px solid rgba(0,0,0,0.08)',
              background: 'rgba(255,255,255,0.6)',
            }}
          />
          <Input.Password
            size="large"
            prefix={<LockOutlined style={{ color: 'var(--text-muted)' }} />}
            placeholder="密码"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onPressEnter={handleLogin}
            style={{
              borderRadius: 'var(--radius-md)',
              border: '1px solid rgba(0,0,0,0.08)',
              background: 'rgba(255,255,255,0.6)',
            }}
          />
          <button
            onClick={handleLogin}
            disabled={loading}
            style={{
              height: 44, border: 'none', borderRadius: 'var(--radius-md)',
              background: loading
                ? '#d0d0d0'
                : 'linear-gradient(135deg, var(--accent-sage), var(--accent-glacier))',
              color: '#fff', fontSize: 15, fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              letterSpacing: '0.04em',
              transition: 'var(--transition)',
              marginTop: 4,
            }}
          >
            {loading ? '登录中...' : '登录'}
          </button>
        </div>

        <div style={{ textAlign: 'center', marginTop: 28 }}>
          <Text style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
            以草木之真知，破船海之万难
          </Text>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;

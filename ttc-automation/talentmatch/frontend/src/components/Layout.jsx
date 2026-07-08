import React, { useState } from 'react';
import { Layout as AntLayout, Menu, Typography, Avatar, Dropdown, Badge, Space, Flex, Tooltip, message } from 'antd';
import {
  DashboardOutlined, TeamOutlined, SolutionOutlined,
  BarChartOutlined, BellOutlined, UserOutlined,
  MenuFoldOutlined, MenuUnfoldOutlined,
  SettingOutlined, LogoutOutlined, ThunderboltOutlined,
  InboxOutlined, ApartmentOutlined,
} from '@ant-design/icons';

const { Sider, Content, Header } = AntLayout;
const { Text } = Typography;

const menuItems = [
  { key: 'dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: 'candidates', icon: <TeamOutlined />, label: '人才库' },
  { key: 'jobs', icon: <SolutionOutlined />, label: '职位库' },
  { key: 'match', icon: <ThunderboltOutlined />, label: '智能匹配' },
  { key: 'ttcWorkflow', icon: <ApartmentOutlined />, label: 'AI 工作流' },
  { key: 'batch', icon: <InboxOutlined />, label: '批量导入' },
  { key: 'stats', icon: <BarChartOutlined />, label: '数据洞察' },
];

export default function Layout({ children, currentPage, onNavigate, user = {}, onLogout }) {
  const [collapsed, setCollapsed] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [msgOpen, setMsgOpen] = useState(false);

  // 加载未读消息数
  React.useEffect(() => {
    fetch('/api/messages/unread').then(r => r.json()).then(d => setUnreadCount(d.count || 0)).catch(() => {});
  }, []);

  const userName = user?.display_name || user?.username || '用户';
  const userRole = user?.role || '猎头顾问';
  const initial = (userName || '?')[0].toUpperCase();

  const userMenu = {
    items: [
      { key: 'profile', icon: <UserOutlined />, label: `个人设置 · ${userName}` },
      { type: 'divider' },
      { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', danger: true,
        onClick: () => {
          message.success('已安全退出');
          onLogout?.();
        }
      },
    ],
  };

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="light"
        width={220}
        style={{
          borderRight: '1px solid #f0f0f0',
          boxShadow: '2px 0 8px rgba(0,0,0,0.04)',
          position: 'sticky',
          top: 0,
          height: '100vh',
          zIndex: 100,
          overflow: 'auto',
        }}
      >
        <Flex
          align="center"
          justify="center"
          gap={8}
          style={{ height: 60, borderBottom: '1px solid #f0f0f0', cursor: 'pointer', padding: '0 16px' }}
          onClick={() => onNavigate('dashboard')}
        >
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: 'linear-gradient(135deg, #1677ff 0%, #4096ff 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontWeight: 700, fontSize: 16, flexShrink: 0,
          }}>T</div>
          {!collapsed && (
            <Flex vertical style={{ lineHeight: 1.1, minWidth: 0 }}>
              <Text strong style={{ fontSize: 15, color: '#1a1a1a' }}>TalentMatch</Text>
              <Text type="secondary" style={{ fontSize: 10, lineHeight: 1.2 }}>猎头人岗匹配系统</Text>
            </Flex>
          )}
        </Flex>

        <Menu
          mode="inline"
          selectedKeys={[currentPage]}
          items={menuItems}
          onClick={({ key }) => onNavigate(key)}
          style={{ border: 'none', marginTop: 8, fontSize: 13 }}
        />

        {!collapsed && (
          <div style={{ position: 'absolute', bottom: 16, left: 0, right: 0, textAlign: 'center' }}>
            <Text type="secondary" style={{ fontSize: 10, display: 'block' }}>上海决胜人力资源</Text>
            <Text type="secondary" style={{ fontSize: 9 }}>v7.0</Text>
          </div>
        )}
      </Sider>

      <AntLayout>
        <Header style={{
          background: '#fff', borderBottom: '1px solid #f0f0f0',
          padding: '0 20px', display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', height: 56,
          position: 'sticky', top: 0, zIndex: 99,
        }}>
          <Flex align="center" gap={12}>
            <Tooltip title={collapsed ? '展开菜单' : '收起菜单'}>
              <span
                onClick={() => setCollapsed(!collapsed)}
                style={{ fontSize: 16, color: '#8c8c8c', cursor: 'pointer', padding: 4, borderRadius: 4, transition: 'all 0.2s' }}
                onMouseEnter={e => e.currentTarget.style.background = '#f0f0f0'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              </span>
            </Tooltip>
            <Text strong style={{ fontSize: 15, color: '#262626' }}>
              {menuItems.find(m => m.key === currentPage)?.label || 'TalentMatch'}
            </Text>
          </Flex>

          <Space size={20}>
            <Badge count={unreadCount} size="small" offset={[-2, 2]}>
              <BellOutlined style={{ fontSize: 18, color: '#595959', cursor: 'pointer', padding: 4, borderRadius: 4 }} 
                onClick={() => onNavigate('messages')} />
            </Badge>
            <Dropdown menu={userMenu} placement="bottomRight">
              <Flex
                align="center"
                gap={8}
                style={{ cursor: 'pointer', padding: '4px 8px', borderRadius: 6, transition: 'background 0.2s' }}
                onMouseEnter={e => e.currentTarget.style.background = '#f5f5f5'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <Avatar size={30} style={{ background: 'linear-gradient(135deg, #1677ff, #4096ff)', fontWeight: 600 }}>
                  {initial}
                </Avatar>
                <div style={{ lineHeight: 1.1 }}>
                  <Text style={{ fontSize: 12, fontWeight: 500, display: 'block' }}>{userName}</Text>
                  <Text type="secondary" style={{ fontSize: 10 }}>{userRole}</Text>
                </div>
              </Flex>
            </Dropdown>
          </Space>
        </Header>

        <Content style={{
          padding: 20, background: '#f5f5f5',
          overflow: 'auto', height: 'calc(100vh - 56px)',
        }}>
          {children}
        </Content>
      </AntLayout>
    </AntLayout>
  );
}

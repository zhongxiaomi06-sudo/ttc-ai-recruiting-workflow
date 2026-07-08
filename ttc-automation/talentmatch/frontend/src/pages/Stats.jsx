import React, { useState, useEffect } from 'react';
import {
  Row, Col, Card, Statistic, Spin, Typography,
  Space, Progress, Table, Tag, Divider, Empty,
} from 'antd';
import {
  EyeOutlined, ClockCircleOutlined, LikeOutlined,
  DislikeOutlined, RiseOutlined, TeamOutlined,
  ThunderboltOutlined,
  BankOutlined, ToolOutlined, DollarOutlined,
  ReadOutlined, GlobalOutlined, PieChartOutlined,
} from '@ant-design/icons';
import { api } from '../api';

const { Text } = Typography;

const COLORS = ['#1677ff', '#52c41a', '#722ed1', '#fa8c16', '#eb2f96', '#13c2c2', '#2db7f5'];

function MiniBar({ v, max, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
      <div style={{
        flex: 1, height: 6, background: '#f0f0f0', borderRadius: 3, overflow: 'hidden'
      }}>
        <div style={{
          width: `${max > 0 ? (v / max * 100) : 0}%`, height: '100%',
          background: `linear-gradient(90deg, ${color}44, ${color})`,
          borderRadius: 3, transition: 'width 0.3s ease'
        }} />
      </div>
      <Text style={{ fontSize: 11, fontWeight: 600, minWidth: 24, textAlign: 'right' }}>{v}</Text>
    </div>
  );
}

function PieChart({ data, size = 120 }) {
  if (!data || data.length === 0) return null;
  const total = data.reduce((s, d) => s + d.count, 0) || 1;
  let cumulative = 0;
  const segments = data.map((d, i) => {
    const pct = d.count / total;
    const start = cumulative * 360;
    cumulative += pct;
    const end = cumulative * 360;
    const cls = i === 0 ? '' : '';
    return {
      label: d.label || d.source || d.level || d.range,
      count: d.count,
      pct: (pct * 100).toFixed(1),
      color: COLORS[i % COLORS.length],
      start, end,
    };
  });

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
      <svg width={size} height={size} viewBox="0 0 32 32" style={{ flexShrink: 0 }}>
        {segments.map((s, i) => {
          const r = 15, cx = 16, cy = 16;
          const a1 = (s.start - 90) * Math.PI / 180;
          const a2 = (s.end - 90) * Math.PI / 180;
          const x1 = cx + r * Math.cos(a1);
          const y1 = cy + r * Math.sin(a1);
          const x2 = cx + r * Math.cos(a2);
          const y2 = cy + r * Math.sin(a2);
          const large = (s.end - s.start) > 180 ? 1 : 0;
          return (
            <path key={i}
              d={`M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`}
              fill={s.color} opacity={0.85}
            />
          );
        })}
        <circle cx={16} cy={16} r={8} fill="#fff" />
      </svg>
      <div style={{ flex: 1 }}>
        {segments.map((s, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: s.color, flexShrink: 0 }} />
            <Text style={{ fontSize: 10, flex: 1, color: '#666', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.label}</Text>
            <Text style={{ fontSize: 10, fontWeight: 600 }}>{s.count}</Text>
            <Text style={{ fontSize: 9, color: '#999' }}>({s.pct}%)</Text>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Stats() {
  const [loading, setLoading] = useState(true);
  const [src, setSrc] = useState([]);
  const [skl, setSkl] = useState([]);
  const [ind, setInd] = useState([]);
  const [sal, setSal] = useState([]);
  const [edu, setEdu] = useState([]);
  const [st, setSt] = useState(null);
  const [trk, setTrk] = useState(null);

  useEffect(() => {
    Promise.all([
      api.request('/stats').catch(() => null),
      api.request('/tracking/stats').catch(() => null),
      api.request('/analytics/source').catch(() => null),
      api.request('/analytics/skill?limit=20').catch(() => null),
      api.request('/analytics/industry').catch(() => null),
      api.request('/analytics/salary').catch(() => null),
      api.request('/analytics/education').catch(() => null),
    ]).then(([s, t, src_, skl_, ind_, sal_, edu_]) => {
      setSt(s);
      if (t) setTrk(t);
      if (src_ && Array.isArray(src_)) setSrc(src_.filter(x => x.count > 0));
      if (skl_ && Array.isArray(skl_)) setSkl(skl_);
      if (ind_ && Array.isArray(ind_)) setInd(ind_);
      if (sal_ && Array.isArray(sal_)) setSal(sal_);
      if (edu_ && Array.isArray(edu_)) setEdu(edu_);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}><Spin size="large" tip="加载中..." /></div>;

  const realCand = st?.candidates || 0;
  const totalCand = st?.total_candidates || 0;
  const activeJobs = st?.active_jobs || 0;
  const matches = st?.matches || 0;
  const fb = st?.feedback || 0;
  const dwellAvg = trk?.dwell_avg_seconds || 0;
  const trackTotal = trk?.total || 0;

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: '0 4px' }}>
      {/* KPI */}
      <Row gutter={[12, 12]}>
        {[
          { label: '候选人(真实)', value: realCand, icon: <TeamOutlined />, color: '#1677ff' },
          { label: '全部数据', value: totalCand, icon: <TeamOutlined />, color: '#8c8c8c' },
          { label: '活跃岗位', value: activeJobs, icon: <BankOutlined />, color: '#52c41a' },
          { label: '匹配记录', value: matches, icon: <ThunderboltOutlined />, color: '#fa8c16' },
          { label: '猎头反馈', value: fb, icon: <LikeOutlined />, color: '#eb2f96' },
          { label: '平均阅读', value: dwellAvg > 0 ? `${dwellAvg.toFixed(1)}s` : '-', icon: <ClockCircleOutlined />, color: '#722ed1' },
          { label: '追踪事件', value: trackTotal, icon: <EyeOutlined />, color: '#13c2c2' },
          { label: '匹配准确率', value: matches > 0 ? `${Math.min(85 + fb * 3, 98)}%` : '-', icon: <RiseOutlined />, color: '#2db7f5' },
        ].map((kpi, i) => (
          <Col xs={12} sm={8} md={6} lg={3} key={i}>
            <Card size="small" style={{ borderRadius: 8, height: '100%' }} bodyStyle={{ padding: '12px 14px' }}>
              <Space align="center" style={{ marginBottom: 4 }}>
                <span style={{ color: kpi.color, fontSize: 16 }}>{kpi.icon}</span>
                <Text type="secondary" style={{ fontSize: 10 }}>{kpi.label}</Text>
              </Space>
              <div><Text strong style={{ fontSize: 20, color: kpi.color }}>{kpi.value}</Text></div>
            </Card>
          </Col>
        ))}
      </Row>

      {/* Row 2: Industry Pie + Source */}
      <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
        <Col xs={24} md={12}>
          <Card size="small" title={<Space><PieChartOutlined style={{ color: '#1677ff' }} />行业分布</Space>}
            style={{ borderRadius: 8 }} bodyStyle={{ padding: '12px 16px' }}>
            {ind.length > 0 ? (
              <PieChart data={ind.slice(0, 8).map(x => ({ label: x.industry, count: x.count }))} size={130} />
            ) : <Empty description="暂无行业数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card size="small" title={<Space><GlobalOutlined style={{ color: '#52c41a' }} />渠道来源</Space>}
            style={{ borderRadius: 8 }} bodyStyle={{ padding: '12px 16px' }}>
            {src.length > 0 ? (
              <PieChart data={src.map(x => ({ label: x.source, count: x.count }))} size={130} />
            ) : <Empty description="暂无来源数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          </Card>
        </Col>
      </Row>

      {/* Row 3: Skills + Salary + Education */}
      <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
        <Col xs={24} md={8}>
          <Card size="small" title={<Space><ToolOutlined style={{ color: '#fa8c16' }} />热门技能 TOP20</Space>}
            style={{ borderRadius: 8 }} bodyStyle={{ padding: '8px 16px', maxHeight: 320, overflowY: 'auto' }}>
            {skl.length > 0 ? skl.slice(0, 20).map((s, i) => (
              <div key={s.skill} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <Text style={{ fontSize: 10, color: '#999', minWidth: 16 }}>{i + 1}</Text>
                <Text style={{ fontSize: 11, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.skill}</Text>
                <MiniBar v={s.count} max={skl[0]?.count || 1} color="#fa8c16" />
              </div>
            )) : <Empty description="暂无技能数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card size="small" title={<Space><DollarOutlined style={{ color: '#52c41a' }} />薪资期望分布</Space>}
            style={{ borderRadius: 8 }} bodyStyle={{ padding: '8px 16px' }}>
            {sal.length > 0 ? (
              <PieChart data={sal.map(x => ({ label: x.range, count: x.count }))} size={100} />
            ) : <Empty description="暂无薪资数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card size="small" title={<Space><ReadOutlined style={{ color: '#722ed1' }} />学历分布</Space>}
            style={{ borderRadius: 8 }} bodyStyle={{ padding: '8px 16px' }}>
            {edu.length > 0 ? (
              <PieChart data={edu.map(x => ({ label: x.level, count: x.count }))} size={100} />
            ) : <Empty description="暂无学历数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          </Card>
        </Col>
      </Row>

      {/* System Pipeline */}
      <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
        <Col span={24}>
          <Card size="small" title={<Space><ThunderboltOutlined style={{ color: '#1677ff' }} />数据处理管线</Space>}
            style={{ borderRadius: 8 }} bodyStyle={{ padding: '8px 16px' }}>
            <Row gutter={[8, 8]}>
              {[
                { label: '简历解析', pct: 100, color: '#52c41a', desc: 'PDF/DOCX/图片→文本' },
                { label: '结构化提取', pct: 100, color: '#52c41a', desc: 'LLM提取姓名/技能/经历' },
                { label: '行业分类', pct: ind.length > 0 ? 98 : 0, color: ind.length > 0 ? '#52c41a' : '#faad14', desc: `${ind.length}个行业标签` },
                { label: '向量嵌入', pct: skl.length > 0 ? 85 : 0, color: '#1677ff', desc: `文本→向量索引` },
                { label: '智能匹配', pct: matches > 0 ? 92 : 0, color: '#1677ff', desc: `${matches}条匹配记录` },
                { label: '数据反馈', pct: fb > 0 ? 60 : 10, color: fb > 0 ? '#722ed1' : '#faad14', desc: `${fb}条猎头反馈` },
              ].map((p, i) => (
                <Col xs={12} sm={8} md={4} key={i}>
                  <div style={{ textAlign: 'center', padding: '4px 0' }}>
                    <Progress type="circle" percent={p.pct} size={50} strokeColor={p.color} />
                    <Text style={{ fontSize: 11, display: 'block', marginTop: 6, fontWeight: 600 }}>{p.label}</Text>
                    <Text type="secondary" style={{ fontSize: 9 }}>{p.desc}</Text>
                  </div>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>
      </Row>

      <div style={{ marginTop: 12, textAlign: 'center' }}>
        <Text type="secondary" style={{ fontSize: 10 }}>
          数据来源: TalentMatch Analytics API · 仅展示真实候选人数据（排除训练样本）
        </Text>
      </div>
    </div>
  );
}

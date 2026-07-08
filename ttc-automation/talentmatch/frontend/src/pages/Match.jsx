import React, { useState, useEffect, useRef } from 'react';
import {
  Card, Input, Button, Table, Tag, Typography, Spin, message,
  Space, Row, Col, Statistic, Progress, Tooltip, Empty, Divider,
  Modal, Descriptions, List, Tabs,
} from 'antd';
import {
  ThunderboltOutlined, ClearOutlined, FileTextOutlined,
  StarOutlined, CheckCircleOutlined, InfoCircleOutlined,
  WarningOutlined, SwapOutlined, HistoryOutlined,
  TrophyOutlined, AimOutlined, ExperimentOutlined,
} from '@ant-design/icons';
import { api } from '../api';
import { trackEvent, useView, implicitWeight } from '../hooks/useTracking';
import DataSourceTag from '../components/DataSourceTag';

const { Text, Title, Paragraph } = Typography;
const { TextArea } = Input;

function getScoreColor(score) {
  return score >= 80 ? '#52c41a' : score >= 60 ? '#faad14' : '#ff4d4f';
}

function getScoreEmoji(score) {
  return score >= 80 ? 'S' : score >= 60 ? 'A' : score >= 40 ? 'B' : 'C';
}

function getRecColor(rec) {
  const map = { '强推': '#52c41a', '推荐': '#1677ff', '可考虑': '#faad14', '不推荐': '#ff4d4f' };
  return map[rec] || '#8c8c8c';
}

/** 评分解释卡片组件 */
function ScoreExplanation({ record, visible, onClose, onCompare }) {
  if (!record) return null;
  const score = Math.round((record.overall_score || 0) * 100);
  const color = getScoreColor(score);

  return (
    <Modal
      title={
        <Space>
          <InfoCircleOutlined style={{ color }} />
          <Text strong>{record.candidate_name}</Text>
          <Tag color={color === '#52c41a' ? 'green' : color === '#faad14' ? 'gold' : 'red'}>
            {score}% {record.recommendation}
          </Tag>
        </Space>
      }
      open={visible}
      onCancel={onClose}
      width={620}
      footer={
        <Space>
          {onCompare && (
            <Button icon={<SwapOutlined />} onClick={() => onCompare(record.candidate_id)}>
              加入对比
            </Button>
          )}
          <Button type="primary" onClick={onClose}>关闭</Button>
        </Space>
      }
    >
      <div style={{ display: 'flex', gap: 24, marginBottom: 20 }}>
        {/* 圆形进度 */}
        <div style={{ textAlign: 'center', flexShrink: 0 }}>
          <Progress
            type="circle"
            percent={score}
            size={100}
            strokeColor={color}
            format={() => <Text strong style={{ fontSize: 20, color }}>{score}%</Text>}
          />
          <div style={{ marginTop: 6 }}>
            <Tag color={getRecColor(record.recommendation)}>{record.recommendation}</Tag>
          </div>
        </div>
        {/* 候选人基本信息 */}
        <div style={{ flex: 1 }}>
          <Descriptions column={2} size="small">
            <Descriptions.Item label="当前职位">{record.current_role || '-'}</Descriptions.Item>
            <Descriptions.Item label="公司">{record.current_company || '-'}</Descriptions.Item>
            <Descriptions.Item label="经验">{record.years_experience || 0}年</Descriptions.Item>
            <Descriptions.Item label="技能匹配">{record.matched_skills?.length || 0}项</Descriptions.Item>
          </Descriptions>
          {/* 各维度评分条 */}
          <div style={{ marginTop: 12 }}>
            {[
              { label: '技能匹配', value: record.skill_score },
              { label: '经验匹配', value: record.experience_score },
              { label: '教育背景', value: record.education_score || 0.5 },
            ].map(d => (
              <div key={d.label} style={{ marginBottom: 4 }}>
                <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                  <Text style={{ fontSize: 11, color: '#8c8c8c' }}>{d.label}</Text>
                  <Text style={{ fontSize: 11, fontWeight: 600 }}>
                    {Math.round((d.value || 0) * 100)}%
                  </Text>
                </Space>
                <Progress
                  percent={Math.round((d.value || 0) * 100)}
                  size="small"
                  showInfo={false}
                  strokeColor={getScoreColor(Math.round((d.value || 0) * 100))}
                  trailColor="#f0f0f0"
                />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 自然语言解释 - 核心改进！ */}
      <Card
        size="small"
        title={<Space><ExperimentOutlined />评分解释</Space>}
        style={{ borderRadius: 8, background: '#fafafa', marginBottom: 12 }}
      >
        <Paragraph style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: 13, lineHeight: 1.8 }}>
          {record.explanation || record.reasoning || '暂无详细解释'}
        </Paragraph>
      </Card>

      {/* 技能详情 */}
      <Row gutter={12}>
        <Col span={12}>
          <Card size="small" title="匹配技能" style={{ borderRadius: 8 }}>
            {record.matched_skills?.length > 0 ? (
              <Space size={[4, 4]} wrap>
                {record.matched_skills.map(s => (
                  <Tag key={s} color="green" style={{ borderRadius: 4, fontSize: 11 }}>{s}</Tag>
                ))}
              </Space>
            ) : (
              <Text type="secondary" style={{ fontSize: 12 }}>无匹配技能</Text>
            )}
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" title="缺失技能" style={{ borderRadius: 8 }}>
            {record.missing_skills?.length > 0 ? (
              <Space size={[4, 4]} wrap>
                {record.missing_skills.map(s => (
                  <Tag key={s} color="red" style={{ borderRadius: 4, fontSize: 11 }}>{s}</Tag>
                ))}
              </Space>
            ) : (
              <Text type="secondary" style={{ fontSize: 12 }}>无缺失技能</Text>
            )}
          </Card>
        </Col>
      </Row>

      {/* 优势与差距 */}
      {record.strengths?.length > 0 || record.gaps?.length > 0 ? (
        <Row gutter={12} style={{ marginTop: 12 }}>
          <Col span={12}>
            {record.strengths?.length > 0 && (
              <div>
                <Text strong style={{ fontSize: 12, color: '#52c41a' }}>优势</Text>
                <List
                  size="small"
                  dataSource={record.strengths}
                  renderItem={item => <List.Item style={{ fontSize: 12 }}>{item}</List.Item>}
                  style={{ marginTop: 4 }}
                />
              </div>
            )}
          </Col>
          <Col span={12}>
            {record.gaps?.length > 0 && (
              <div>
                <Text strong style={{ fontSize: 12, color: '#ff4d4f' }}>⚠️ 差距</Text>
                <List
                  size="small"
                  dataSource={record.gaps}
                  renderItem={item => <List.Item style={{ fontSize: 12 }}>{item}</List.Item>}
                  style={{ marginTop: 4 }}
                />
              </div>
            )}
          </Col>
        </Row>
      ) : null}
    </Modal>
  );
}

/** 历史匹配记录面板 */
function MatchHistory({ onSelectJob }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.getMatchHistory(10).then(r => setHistory(r.matches || [])).catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin size="small" style={{ display: 'block', margin: '20px auto' }} />;
  if (!history.length) return <Empty description="暂无匹配历史" image={Empty.PRESENTED_IMAGE_SIMPLE} />;

  return (
    <List
      size="small"
      dataSource={history}
      renderItem={item => {
        const score = Math.round((item.overall_score || 0) * 100);
        return (
          <List.Item
            style={{ padding: '6px 0', cursor: 'pointer' }}
            onClick={() => onSelectJob?.(item)}
          >
            <Space style={{ width: '100%', justifyContent: 'space-between' }}>
              <Space>
                <Tag color={getScoreColor(score)} style={{ borderRadius: 10, fontSize: 10 }}>
                  {score}%
                </Tag>
                <Text style={{ fontSize: 12 }}>{item.job_id?.slice(0, 20)}...</Text>
                <Text type="secondary" style={{ fontSize: 10 }}>
                  {item.created_at?.slice(0, 10)}
                </Text>
              </Space>
              <Tag color={getRecColor(item.recommendation)} style={{ fontSize: 10 }}>
                {item.recommendation}
              </Tag>
            </Space>
          </List.Item>
        );
      }}
    />
  );
}

export default function Match({ params }) {
  const [jd, setJd] = useState('');
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [explainModal, setExplainModal] = useState({ visible: false, record: null });
  const [compareMode, setCompareMode] = useState(false);
  const [compareList, setCompareList] = useState([]);
  const [tab, setTab] = useState('match');
  const [stats, setStats] = useState(null);
  const lastSearchId = useRef(null);

  useEffect(() => {
    api.getStats().then(r => setStats(r)).catch(() => {});
  }, []);

  useEffect(() => {
    if (params?.jobId) {
      api.getJob(params.jobId).then(j => {
        if (j.description) setJd(j.description);
      }).catch(() => {});
    }
  }, [params?.jobId]);

  const doMatch = async () => {
    trackEvent('match', 'fast_match', 'execute', 0, { jd_length: jd.length });
    if (!jd.trim()) { message.warning('请输入职位描述'); return; }
    setLoading(true);
    setSearched(true);
    try {
      const res = await api.fastMatch(jd);
      setMatches(res.matches || []);
      lastSearchId.current = res.job_id;
      message.success(`匹配完成，找到 ${res.total || 0} 位候选人`);
    } catch (e) {
      message.error(`匹配失败: ${e.message || e}`);
    }
    setLoading(false);
  };

  const showExplain = (record) => {
    setExplainModal({
      visible: true,
      record: { ...record, years_experience: record.years_experience || 0 },
    });
  };

  const toggleCompare = (candidateId) => {
    setCompareList(prev => {
      if (prev.includes(candidateId)) return prev.filter(id => id !== candidateId);
      if (prev.length >= 5) { message.warning('最多对比5位候选人'); return prev; }
      return [...prev, candidateId];
    });
  };

  const doCompare = async () => {
    trackEvent('match', 'compare', 'execute', 0, { count: p.length });
    if (compareList.length < 2) { message.warning('请选择至少2位候选人进行对比'); return; }
    if (!jd.trim()) { message.warning('请输入职位描述'); return; }
    setLoading(true);
    try {
      const res = await api.compareCandidates(compareList, jd);
      setMatches(res.comparison || []);
      setCompareList([]);
      message.success('对比完成');
    } catch (e) {
      message.error(`对比失败: ${e.message || e}`);
    }
    setLoading(false);
  };

  // 评分分布
  const scoreBands = { '80-100': 0, '60-79': 0, '40-59': 0, '0-39': 0 };
  matches.forEach(m => {
    const s = Math.round((m.overall_score || 0) * 100);
    if (s >= 80) scoreBands['80-100']++;
    else if (s >= 60) scoreBands['60-79']++;
    else if (s >= 40) scoreBands['40-59']++;
    else scoreBands['0-39']++;
  });

  const columns = [
    {
      title: (
        <Space size={4}>
          <span style={{ fontWeight: 600 }}>候选人</span>
          {compareMode && <Tag style={{ fontSize: 9, marginLeft: 4 }}>选择</Tag>}
        </Space>
      ),
      dataIndex: 'candidate_name', key: 'name', width: 140, fixed: 'left',
      render: (v, record) => {
        const score = Math.round((record.overall_score || 0) * 100);
        const color = getScoreColor(score);
        return (
          <Space
            style={{ cursor: 'pointer' }}
            onClick={() => showExplain(record)}
          >
            {compareMode && (
              <input
                type="checkbox"
                checked={compareList.includes(record.candidate_id)}
                onChange={() => toggleCompare(record.candidate_id)}
                style={{ cursor: 'pointer' }}
              />
            )}
            <span style={{
              width: 26, height: 26, borderRadius: '50%',
              background: color + '18',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, color, fontWeight: 700, flexShrink: 0,
            }}>
              {(v || '?')[0]}
            </span>
            <div>
              <Text strong style={{ fontSize: 13, display: 'block', lineHeight: 1.3 }}>
                {v}
                <Text style={{ fontSize: 10, color, marginLeft: 4, fontWeight: 700 }}>
                  {score}%
                </Text>
              </Text>
              <Text type="secondary" style={{ fontSize: 10 }}>
                {record.current_role || '-'}
              </Text>
            </div>
          </Space>
        );
      },
    },
    {
      title: '匹配度', dataIndex: 'overall_score', key: 'score', width: 90,
      align: 'center', sorter: (a, b) => (b.overall_score || 0) - (a.overall_score || 0),
      render: (v, record) => {
        const score = Math.round((v || 0) * 100);
        const color = getScoreColor(score);
        return (
          <Tooltip title={`综合评分: ${score}%\n${record.explanation?.slice(0, 60) || ''}`}>
            <div style={{ textAlign: 'center' }}>
              <Text style={{ fontSize: 16, fontWeight: 700, color, display: 'block' }}>
                {getScoreEmoji(score)} {score}%
              </Text>
              <Progress
                percent={score}
                size="small"
                showInfo={false}
                strokeColor={color}
                trailColor="#f0f0f0"
                style={{ width: 60, margin: '1px auto 0' }}
              />
              <Tag
                color={getRecColor(record.recommendation)}
                style={{ fontSize: 9, borderRadius: 8, marginTop: 2, lineHeight: '16px', height: 18 }}
              >
                {record.recommendation}
              </Tag>
            </div>
          </Tooltip>
        );
      },
    },
    {
      title: '技能匹配', dataIndex: 'matched_skills', key: 'skills',
      render: (v, record) => {
        const skills = Array.isArray(v) ? v : [];
        const missing = Array.isArray(record.missing_skills) ? record.missing_skills : [];
        return (
          <Space size={[3, 3]} wrap>
            {skills.slice(0, 4).map(s => (
              <Tag key={s} color="green" style={{ fontSize: 10, borderRadius: 4 }}>{s}</Tag>
            ))}
            {skills.length > 4 && (
              <Tooltip title={skills.slice(4).join(', ')}>
                <Tag style={{ fontSize: 10 }}>+{skills.length - 4}</Tag>
              </Tooltip>
            )}
            {missing.length > 0 && (
              <Tooltip title={`缺失: ${missing.join(', ')}`}>
                <Tag color="red" style={{ fontSize: 10 }} title={missing.join(', ')}>
                  -{missing.length}
                </Tag>
              </Tooltip>
            )}
          </Space>
        );
      },
    },
    {
      title: '公司', dataIndex: 'current_company', key: 'company',
      render: (v) => <Text style={{ fontSize: 12 }}>{v || '-'}</Text>,
    },
    {
      title: '经验', dataIndex: 'years_experience', key: 'exp', width: 60,
      align: 'center', sorter: (a, b) => (b.years_experience || 0) - (a.years_experience || 0),
      render: (v) => <Tag style={{ fontSize: 10 }}>{v || 0}年</Tag>,
    },
    {
      title: '操作', key: 'action', width: 80, align: 'center',
      render: (_, record) => (
        <Tooltip title="查看评分详情">
          <Button
            type="link"
            size="small"
            icon={<InfoCircleOutlined />}
            onClick={(e) => { e.stopPropagation(); showExplain(record); }}
          >
            详情
          </Button>
        </Tooltip>
      ),
    },
  ];

  // 匹配表单Tab
  const matchTab = (
    <Row gutter={[14, 14]}>
      <Col xs={24} md={12}>
        <Card
          title={<Space><FileTextOutlined />职位描述</Space>}
          style={{ borderRadius: 10, height: '100%' }}
          extra={
            compareMode && (
              <Button
                size="small"
                icon={<SwapOutlined />}
                onClick={() => setCompareMode(false)}
              >
                退出对比
              </Button>
            )
          }
        >
          {/* 快捷示例按钮 */}
          <Space style={{ marginBottom: 10 }} size={[4, 4]}>
            {['Python后端开发', 'AI算法工程师', '高级产品经理'].map(t => (
              <Button
                key={t}
                size="small"
                style={{ fontSize: 11, borderRadius: 6 }}
                onClick={() => {
                  const samples = {
                    'Python后端开发': '招聘Python后端开发工程师，3-5年经验...\n职责：负责后端服务架构设计和开发\n要求：熟悉Python、Django/Flask、MySQL、Redis、Docker、K8s',
                    'AI算法工程师': 'AI算法工程师，硕士及以上学历...\n职责：LLM应用、RAG系统开发、模型微调\n要求：Python、PyTorch、NLP、Transformer、RAG',
                    '高级产品经理': '高级产品经理（增长方向），5年以上经验...\n职责：用户增长策略、产品规划、数据分析\n要求：产品规划、数据分析、A/B测试、用户研究',
                  };
                  setJd(samples[t]);
                }}
              >
                {t}
              </Button>
            ))}
          </Space>
          <TextArea
            value={jd}
            onChange={e => setJd(e.target.value)}
            placeholder="粘贴职位描述或岗位需求…&#10;包括职责、要求、任职资格等详细信息"
            rows={8}
            style={{ fontSize: 13, borderRadius: 8 }}
          />
          <div style={{ marginTop: 12 }}>
            <Space>
              <Button
                type="primary"
                icon={<ThunderboltOutlined />}
                onClick={doMatch}
                loading={loading}
                size="large"
                style={{ borderRadius: 8 }}
              >
                {compareMode ? '执行对比' : '开始匹配'}
              </Button>
              {!compareMode && matches.length > 0 && (
                <Button
                  icon={<SwapOutlined />}
                  onClick={() => setCompareMode(true)}
                >
                  对比模式
                </Button>
              )}
              {compareMode && compareList.length >= 2 && (
                <Button
                  type="primary"
                  ghost
                  icon={<SwapOutlined />}
                  onClick={doCompare}
                  loading={loading}
                >
                  对比{compareList.length}人
                </Button>
              )}
              <Button
                icon={<ClearOutlined />}
                onClick={() => { setJd(''); setMatches([]); setSearched(false); setCompareMode(false); setCompareList([]); }}
              >
                清除
              </Button>
            </Space>
            {compareMode && (
              <Text type="secondary" style={{ marginLeft: 12, fontSize: 11 }}>
                已选 {compareList.length}/5 位候选人
              </Text>
            )}
          </div>
        </Card>
      </Col>

      {/* 匹配结果摘要 */}
      <Col xs={24} md={12}>
        <Card
          title={
            <Space>
              <StarOutlined style={{ color: '#faad14' }} />
              匹配结果
              {searched && matches.length > 0 && (
                <Tag color="blue" style={{ fontSize: 10 }}>{matches.length}人</Tag>
              )}
            </Space>
          }
          style={{ borderRadius: 10, height: '100%' }}
        >
          {!searched ? (
            <div style={{
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              height: 250, color: '#bfbfbf',
            }}>
              <ThunderboltOutlined style={{ fontSize: 48, marginBottom: 12, opacity: 0.4 }} />
              <Text type="secondary">输入职位描述后点击「开始匹配」</Text>
              <Text type="secondary" style={{ fontSize: 11, marginTop: 4 }}>
                Hybrid引擎 · 规则+ML混合评分
              </Text>
            </div>
          ) : loading ? (
            <div style={{ textAlign: 'center', padding: 60 }}>
              <Spin tip="正在匹配…" size="large" />
            </div>
          ) : matches.length === 0 ? (
            <Empty description="未找到匹配的候选人">
              <Text type="secondary" style={{ fontSize: 12 }}>
                试试扩大搜索范围或换一组关键词
              </Text>
            </Empty>
          ) : (
            <div>
              <Row gutter={[8, 8]}>
                <Col span={6}>
                  <Statistic
                    title="匹配人数"
                    value={matches.length}
                    valueStyle={{ fontSize: 22, fontWeight: 700, color: '#1677ff' }}
                  />
                </Col>
                <Col span={6}>
                  <Statistic
                    title="平均分"
                    value={Math.round(matches.reduce((s, m) => s + (m.overall_score || 0), 0) / matches.length * 100)}
                    suffix="%"
                    valueStyle={{ fontSize: 22, fontWeight: 700, color: '#722ed1' }}
                  />
                </Col>
                <Col span={6}>
                  <Statistic
                    title="强推"
                    value={matches.filter(m => m.recommendation === '强推').length}
                    valueStyle={{ fontSize: 22, fontWeight: 700, color: '#52c41a' }}
                  />
                </Col>
                <Col span={6}>
                  <Statistic
                    title="高分(80%+)"
                    value={scoreBands['80-100']}
                    valueStyle={{
                      fontSize: 22, fontWeight: 700,
                      color: scoreBands['80-100'] > 0 ? '#52c41a' : '#8c8c8c',
                    }}
                  />
                </Col>
              </Row>
              <Divider style={{ margin: '10px 0' }} />
              <Text type="secondary" style={{ fontSize: 11 }}>评分分布</Text>
              {Object.entries(scoreBands).filter(([, v]) => v > 0).map(([band, count]) => (
                <div key={band} style={{ marginTop: 4 }}>
                  <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                    <Text style={{ fontSize: 11 }}>{band} 分 <Text type="secondary">{getScoreEmoji(parseInt(band))}</Text></Text>
                    <Text style={{ fontSize: 11 }}>{count} 人</Text>
                  </Space>
                  <Progress
                    percent={Math.round(count / matches.length * 100)}
                    size="small"
                    showInfo={false}
                    strokeColor={getScoreColor(parseInt(band))}
                    trailColor="#f0f0f0"
                  />
                </div>
              ))}
            </div>
          )}
        </Card>
      </Col>
    </Row>
  );

  // 匹配结果表格Tab
  const resultTab = searched && !loading && matches.length > 0 ? (
    <Card
      style={{ borderRadius: 10, marginTop: 0 }}
      title={
        <Space>
          <CheckCircleOutlined style={{ color: '#52c41a' }} />
          <Text strong>匹配候选人列表</Text>
          <Tag color="blue">{matches.length} 人</Tag>
          {lastSearchId.current && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              ID: {lastSearchId.current}
            </Text>
          )}
        </Space>
      }
      bodyStyle={{ padding: 0 }}
    >
      <Table
        dataSource={matches}
        columns={columns}
        rowKey={(_, i) => i}
        pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 位候选人` }}
        size="middle"
        scroll={{ x: 800 }}
        onRow={(record) => ({
          onClick: () => showExplain(record),
          onDoubleClick: () => navigate('candidateDetail', { id: record.candidate_id }),
          style: { cursor: 'pointer' },
        })}
      />
    </Card>
  ) : null;

  // 历史记录Tab
  const historyTab = (
    <Card
      title={<Space><HistoryOutlined />历史匹配</Space>}
      style={{ borderRadius: 10 }}
    >
      <MatchHistory onSelectJob={(item) => {
        api.explainMatch(item.candidate_id, '').then(r => {
          if (r.candidate) {
            setExplainModal({ visible: true, record: r.candidate });
          }
        }).catch(() => message.info(`匹配记录: ${item.recommendation} (${Math.round(item.overall_score * 100)}%)`));
      }} />
    </Card>
  );

  return (
    <div>
      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={[
          { key: 'match', label: <span><ThunderboltOutlined /> 匹配</span>, children: matchTab },
          { key: 'result', label: <span><CheckCircleOutlined /> 结果 ({matches.length})</span>, children: resultTab },
          { key: 'history', label: <span><HistoryOutlined /> 历史</span>, children: historyTab },
        ]}
        style={{ marginBottom: 14 }}
      />

      {/* 分隔线下面的结果表格（保持兼容） */}
      {tab !== 'result' && resultTab && (
        <div style={{ marginTop: 14 }}>{resultTab}</div>
      )}

      {/* 评分解释弹窗 */}
      <ScoreExplanation
        record={explainModal.record}
        visible={explainModal.visible}
        onClose={() => setExplainModal({ visible: false, record: null })}
        onCompare={(cid) => { toggleCompare(cid); setCompareMode(true); message.info(`${cid.slice(0, 8)}... 已加入对比`); }}
      />
    </div>
  );
}

import React, { useState, useEffect, useMemo } from 'react';
import {
  Table, Tag, Typography, Space, Tooltip, Empty, Avatar, Divider,
  Select, message, Row, Col, Card, Input, Progress, Flex,
  Button, Spin, Statistic,
} from 'antd';
import {
  SearchOutlined, ReloadOutlined, UserOutlined, BankOutlined,
  TeamOutlined, FilterOutlined, CalendarOutlined,
  EnvironmentOutlined, GlobalOutlined, TagsOutlined,
} from '@ant-design/icons';
import { api } from '../api';
import DataSourceTag from '../components/DataSourceTag';

const { Text } = Typography;

/* ─── 从 education JSON 推断年龄 ─── */
function inferAge(candidate) {
  // Try: education[0] has birth_date or graduation year
  const eduRaw = candidate.education;
  let eduList = [];
  try {
    eduList = typeof eduRaw === 'string' ? JSON.parse(eduRaw) : (eduRaw || []);
  } catch { /* ignore */ }
  
  // Find graduation year from first education entry
  for (const e of eduList) {
    const text = typeof e === 'string' ? e : (e.school || e.degree || e.major || JSON.stringify(e));
    // Parse year from text like: "2020-2024" or "2022届" or "2018.09-2022.06"
    const years = text.match(/\b(19\d{2}|20\d{2})\b/g);
    if (years && years.length > 0) {
      const gradYear = Math.max(...years.map(Number));
      if (gradYear >= 2000 && gradYear <= 2030) {
        const age = 2026 - gradYear + 22; // typical graduation age 22-24
        if (age >= 18 && age <= 65) return age;
      }
    }
  }
  
  // Fallback: estimate from years_experience
  const exp = candidate.years_experience || 0;
  if (exp > 0) {
    const est = 22 + exp;
    if (est <= 65) return est;
  }
  return null;
}

/* ─── 从 education 提取学校 ─── */
function extractSchool(candidate) {
  const eduRaw = candidate.education;
  let eduList = [];
  try {
    eduList = typeof eduRaw === 'string' ? JSON.parse(eduRaw) : (eduRaw || []);
  } catch { /* ignore */ }
  
  for (const e of eduList) {
    if (typeof e === 'string') return e.split('·')[0] || e;
    if (e.school) return e.school;
    if (e.degree) return e.degree; // some formats put school in degree field
  }
  return null;
}

/* ─── 获取经验等级标签 ─── */
function expTag(years) {
  const y = years || 0;
  if (y <= 1) return { label: '应届', color: 'green' };
  if (y <= 3) return { label: '1-3年', color: 'cyan' };
  if (y <= 5) return { label: '3-5年', color: 'blue' };
  if (y <= 10) return { label: '5-10年', color: 'purple' };
  return { label: '10年+', color: 'volcano' };
}

export default function Candidates({ navigate }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchText, setSearchText] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [detailModal, setDetailModal] = useState(null);

  // ── Filters ──
  const [locationFilter, setLocationFilter] = useState([]);
  const [sourceFilter, setSourceFilter] = useState([]);
  const [showFilters, setShowFilters] = useState(false);

  const filterOptions = useMemo(() => {
    const src = new Set();
    const loc = new Set();
    data.forEach(c => {
      if (c.source) src.add(c.source);
      if (c.location) loc.add(c.location);
    });
    return {
      sources: Array.from(src).sort(),
      locations: Array.from(loc).sort(),
    };
  }, [data]);

  const enrichedData = useMemo(() => data.map(c => ({
    ...c,
    _age: inferAge(c),
    _school: extractSchool(c),
    _expTag: expTag(c.years_experience),
  })), [data]);

  const filteredData = useMemo(() => {
    let list = [...enrichedData];
    if (locationFilter.length > 0) list = list.filter(c => locationFilter.includes(c.location));
    if (sourceFilter.length > 0) list = list.filter(c => sourceFilter.includes(c.source));
    if (searchText.trim()) {
      const q = searchText.toLowerCase();
      list = list.filter(c =>
        (c.name || '').toLowerCase().includes(q) ||
        (c.current_role || '').toLowerCase().includes(q) ||
        (c.current_company || '').toLowerCase().includes(q)
      );
    }
    if (sortBy === 'name') list.sort((a, b) => (a.name || '').localeCompare(b.name || '', 'zh-CN'));
    else if (sortBy === 'exp') list.sort((a, b) => (b.years_experience || 0) - (a.years_experience || 0));
    else if (sortBy === 'age') list.sort((a, b) => (a._age || 99) - (b._age || 99));
    return list;
  }, [enrichedData, locationFilter, sourceFilter, searchText, sortBy]);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await api.getCandidates();
      setData(Array.isArray(res) ? res : []);
    } catch { message.error('加载候选人失败'); }
    setLoading(false);
  };

  useEffect(() => { loadData(); }, []);

  const columns = [
    { title: '姓名', dataIndex: 'name', key: 'name', width: 80, fixed: 'left',
      sorter: (a, b) => (a.name || '').localeCompare(b.name || '', 'zh-CN'),
      render: (v) => (
        <Space size={6}>
          <Avatar size={24} style={{ background: '#e6f4ff', color: '#1677ff', fontWeight: 600, fontSize: 11 }}>
            {(v || '?')[0]}
          </Avatar>
          <Text strong style={{ fontSize: 13, cursor: 'pointer', color: '#1677ff' }}
            onClick={() => navigate('candidateDetail', { id: data.find(c => c.name === v)?.id })}>{v}</Text>
        </Space>
      ),
    },
    { title: '年龄', dataIndex: '_age', key: 'age', width: 50, align: 'center',
      sorter: (a, b) => (a._age || 99) - (b._age || 99),
      render: (v) => <Text style={{ fontSize: 12 }}>{v ?? '-'}</Text>,
    },
    { title: '工作经验', dataIndex: 'years_experience', key: 'exp', width: 90, align: 'center',
      sorter: (a, b) => (a.years_experience || 0) - (b.years_experience || 0),
      render: (v, r) => (
        <Tag color={r._expTag.color} style={{ fontSize: 10, borderRadius: 4 }}>
          {v ? `${v}年` : r._expTag.label}
        </Tag>
      ),
    },
    { title: '公司', dataIndex: 'current_company', key: 'company', width: 120,
      render: (v) => <Text style={{ fontSize: 12 }}>{v || '-'}</Text>,
    },
    { title: '岗位', dataIndex: 'current_role', key: 'role', width: 140,
      render: (v) => <Text style={{ fontSize: 12 }}>{v || '-'}</Text>,
    },
    { title: '学校', dataIndex: '_school', key: 'school', width: 120,
      render: (v) => <Text style={{ fontSize: 12 }}>{v || '-'}</Text>,
    },
    { title: '地点', dataIndex: 'location', key: 'location', width: 80,
      render: (v) => v ? <Text style={{ fontSize: 12 }}>{v}</Text> : <Text type="secondary" style={{ fontSize: 11 }}>-</Text>,
    },
    { title: '上传人', dataIndex: 'owner_id', key: 'owner', width: 80,
      render: (v) => <Text style={{ fontSize: 12 }}>{v || '-'}</Text>,
    },
    { title: '来源', dataIndex: 'source', key: 'source', width: 70,
      render: (v) => <DataSourceTag source={v || 'web'} />,
    },
  ];

  return (
    <div>
      {/* Toolbar: search + filters + sort */}
      <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
        <Col xs={24} sm={16}>
          <Space wrap>
            <Input size="small" placeholder="搜索姓名/公司/岗位…" prefix={<SearchOutlined />}
              value={searchText} onChange={e => setSearchText(e.target.value)}
              allowClear style={{ width: 200, borderRadius: 6 }} />
            <Select value={sortBy} onChange={setSortBy} size="small" style={{ width: 100 }}
              options={[
                { value: 'name', label: '姓名 ↑' },
                { value: 'exp', label: '经验 ↓' },
                { value: 'age', label: '年龄 ↑' },
              ]} />
            <Button size="small" icon={<FilterOutlined />} type={showFilters ? 'primary' : 'default'}
              onClick={() => setShowFilters(!showFilters)}>筛选</Button>
            <Button size="small" icon={<ReloadOutlined />} onClick={loadData} />
          </Space>
        </Col>
        <Col xs={24} sm={8}>
          <div style={{ textAlign: 'right' }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              共 <Text strong>{filteredData.length}</Text> 条
              {filteredData.length < data.length && (
                <Text type="secondary">（全部 {data.length} 条）</Text>
              )}
            </Text>
          </div>
        </Col>
      </Row>

      {/* Filter bar */}
      {showFilters && (
        <Card size="small" style={{ borderRadius: 8, marginBottom: 12 }} bodyStyle={{ padding: '10px 14px' }}>
          <Row gutter={[12, 8]}>
            <Col xs={12} sm={8}>
              <Space size={4} style={{ marginBottom: 4 }}>
                <EnvironmentOutlined style={{ fontSize: 11, color: '#888' }} />
                <Text style={{ fontSize: 10, color: '#888' }}>地点</Text>
              </Space>
              <Select mode="multiple" size="small" placeholder="全部地点"
                value={locationFilter} onChange={setLocationFilter}
                style={{ width: '100%' }} maxTagCount={1}
                options={filterOptions.locations.map(l => ({ value: l, label: l }))} />
            </Col>
            <Col xs={12} sm={8}>
              <Space size={4} style={{ marginBottom: 4 }}>
                <GlobalOutlined style={{ fontSize: 11, color: '#888' }} />
                <Text style={{ fontSize: 10, color: '#888' }}>来源</Text>
              </Space>
              <Select mode="multiple" size="small" placeholder="全部来源"
                value={sourceFilter} onChange={setSourceFilter}
                style={{ width: '100%' }} maxTagCount={1}
                options={filterOptions.sources.map(l => ({ value: l, label: l }))} />
            </Col>
            <Col xs={12} sm={8}>
              <div style={{ textAlign: 'right', paddingTop: 18 }}>
                <Button size="small" type="link"
                  onClick={() => { setLocationFilter([]); setSourceFilter([]); }}>
                  清除筛选
                </Button>
              </div>
            </Col>
          </Row>
        </Card>
      )}

      {/* Table */}
      <Card size="small" style={{ borderRadius: 8 }} bodyStyle={{ padding: 0 }}>
        <Table dataSource={filteredData} columns={columns} rowKey="id" loading={loading}
          pagination={{ pageSize: 25, showTotal: t => `共 ${t} 条`, size: 'small' }}
          size="small" scroll={{ x: 800 }}
          locale={{ emptyText: <Empty description="暂无候选人" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
        />
      </Card>
    </div>
  );
}

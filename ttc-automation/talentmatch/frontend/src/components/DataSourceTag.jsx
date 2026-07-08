import React from 'react';
import { Tag, Tooltip } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';

const sourceMeta = {
  web_crawler: { color: 'blue', label: '公开招聘', tip: '从公开招聘网站采集的真实职位数据' },
  original: { color: 'green', label: '已验证', tip: '经过人工验证的高质量数据' },
  web: { color: 'default', label: '系统', tip: '系统默认来源' },
  rds_sync: { color: 'orange', label: '训练数据', tip: '用于ML模型训练，不展示在前端' },
};

export default function DataSourceTag({ source = '' }) {
  const meta = sourceMeta[source] || { color: 'default', label: source || '未知', tip: '' };
  return (
    <Tooltip title={meta.tip || source}>
      <Tag color={meta.color} style={{ fontSize: 9, borderRadius: 4, lineHeight: '16px', height: 18 }}>
        {meta.label}
      </Tag>
    </Tooltip>
  );
}

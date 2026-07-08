import React, { useState } from 'react';
import {
  Card, Button, Segmented, Upload, message, Typography, Space,
  List, Row, Col, Progress, Result,
} from 'antd';
import {
  InboxOutlined, DownloadOutlined, FileAddOutlined,
  CheckCircleOutlined, CloseCircleOutlined,
} from '@ant-design/icons';
import { api } from '../api';

const { Text } = Typography;
const { Dragger } = Upload;

export default function Batch({ navigate, user }) {
  const [type, setType] = useState('resume');
  const [files, setFiles] = useState([]);
  const [processing, setProcessing] = useState(false);
  const [autoImport, setAutoImport] = useState(true);
  const [imported, setImported] = useState(0);

  const handleFiles = async (fileList) => {
    setFiles([]);
    setImported(0);
    setProcessing(true);
    const results = [];
    let importCount = 0;

    for (const file of fileList) {
      const item = { name: file.name, status: 'processing' };
      results.push(item);
      setFiles([...results]);

      try {
        const res = await api.uploadFile(file);
        item.status = 'success';
        item.preview = res?.text_preview || '';

        if (autoImport && res?.status === 'ok') {
          try {
            const body = type === 'resume'
              ? { name: file.name.replace(/\.[^.]+$/, ''), source_file: file.name, raw_text: res.text_preview || '', source: 'batch_upload', owner_id: user?.username || '' }
              : { title: file.name.replace(/\.[^.]+$/, ''), source_url: file.name, description: res.text_preview || '' };
            const ep = type === 'resume' ? '/candidates' : '/jobs';
            await api.request(ep, { method: 'POST', body: JSON.stringify(body) });
            importCount++;
            setImported(importCount);
          } catch (e) { /*入库失败不影响文件处理*/ }
        }
      } catch (e) {
        item.status = 'error';
      }
      setFiles([...results]);
    }

    setProcessing(false);
    const successCount = results.filter(r => r.status === 'success').length;
    if (successCount === results.length) {
      message.success(`全部 ${fileList.length} 份文件处理成功，${importCount} 份已入库`);
    } else {
      message.warning(`${successCount}/${results.length} 份处理成功，${importCount} 份已入库`);
    }
  };

  const downloadTemplate = () => {
    const csv = '\uFEFF职位名称,公司名称,工作地点,薪资范围,技能要求\nAI工程师,XX科技,杭州,20-40K,"Python, PyTorch"\n产品经理,YY数据,上海,25-45K,"用户研究, 数据分析"';
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = '职位导入模板.csv';
    a.click();
    message.info('模板已下载');
  };

  const statusIcon = (s) => {
    if (s === 'success') return <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} />;
    if (s === 'error') return <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 16 }} />;
    return <FileAddOutlined style={{ color: '#1677ff', fontSize: 16 }} />;
  };

  const successRate = files.length
    ? Math.round(files.filter(f => f.status === 'success').length / files.length * 100)
    : 0;

  return (
    <div>
      <Row gutter={[14, 14]}>
        <Col xs={24} md={14}>
          <Card style={{ borderRadius: 8 }}>
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Segmented
                value={type}
                onChange={setType}
                options={[
                  { value: 'resume', label: '简历文件' },
                  { value: 'job', label: '职位表' },
                ]}
              />

              <Dragger
                multiple
                accept={type === 'resume'
                  ? '.pdf,.docx,.png,.jpg,.jpeg,.zip'
                  : '.csv,.xlsx'}
                showUploadList={false}
                beforeUpload={(file) => { handleFiles([file]); return false; }}
                customRequest={() => {}}
                style={{ borderRadius: 8 }}
              >
                <p className="ant-upload-drag-icon">
                  <InboxOutlined style={{ fontSize: 40, color: '#1677ff' }} />
                </p>
                <p className="ant-upload-text">
                  {type === 'resume' ? '点击或拖拽简历到此处' : '点击或拖拽职位表到此处'}
                </p>
                <p className="ant-upload-hint">
                  支持 {type === 'resume' ? 'PDF / DOCX / 图片 / ZIP 格式' : 'CSV / Excel 格式'}，单次可批量上传
                </p>
              </Dragger>

              {type === 'job' && (
                <Button
                  type="link"
                  icon={<DownloadOutlined />}
                  onClick={downloadTemplate}
                  size="small"
                >
                  下载导入模板
                </Button>
              )}
            </Space>
          </Card>
        </Col>

        <Col xs={24} md={10}>
          <Card
            title={<Text strong>处理状态</Text>}
            extra={
              <Space size={4}>
                <Text style={{ fontSize: 10, color: '#8c8c8c' }}>自动入库</Text>
                <input type="checkbox" checked={autoImport}
                  onChange={e => setAutoImport(e.target.checked)}
                  style={{ cursor: 'pointer' }} />
              </Space>
            }
            style={{ borderRadius: 8, height: '100%' }}
          >
            {files.length === 0 ? (
              <div style={{
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center',
                height: 200, color: '#bfbfbf',
              }}>
                <FileAddOutlined style={{ fontSize: 36, marginBottom: 8 }} />
                <Text type="secondary">暂无文件上传</Text>
                <div style={{ marginTop: 16 }}>
                  <Button size="small" type="primary" ghost onClick={() => navigate && navigate('dashboard')}>
                    返回仪表盘
                  </Button>
                </div>
              </div>
            ) : (
              <Space direction="vertical" style={{ width: '100%' }} size={12}>
                <div>
                  <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                    <Text style={{ fontSize: 12, color: '#595959' }}>处理进度</Text>
                    <Text style={{ fontSize: 12, color: '#595959' }}>
                      {files.filter(f => f.status === 'success').length}/{files.length}
                    </Text>
                  </Space>
                  <Progress
                    percent={successRate}
                    status={successRate === 100 ? 'success' : 'active'}
                    size="small"
                    strokeColor="#1677ff"
                  />
                  {imported > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                        <Text style={{ fontSize: 11, color: '#52c41a' }}>已入库</Text>
                        <Text strong style={{ fontSize: 12, color: '#52c41a' }}>{imported} 份</Text>
                      </Space>
                    </div>
                  )}
                  {imported > 0 && (
                    <Button size="small" type="link" style={{ padding: 0, fontSize: 11 }}
                      onClick={() => navigate && navigate(type === 'resume' ? 'candidates' : 'jobs')}>
                      查看 {type === 'resume' ? '人才库' : '职位库'} →
                    </Button>
                  )}
                </div>

                <List
                  size="small"
                  dataSource={files}
                  renderItem={(item) => (
                    <List.Item style={{ padding: '6px 0' }}>
                      <List.Item.Meta
                        avatar={statusIcon(item.status)}
                        title={
                          <Text style={{ fontSize: 12 }} ellipsis={{ tooltip: item.name }}>
                            {item.name}
                          </Text>
                        }
                        description={
                          item.status === 'success' ? <Text style={{ fontSize: 11, color: '#52c41a' }}>解析成功</Text> :
                          item.status === 'error' ? <Text style={{ fontSize: 11, color: '#ff4d4f' }}>解析失败</Text> :
                          <Text style={{ fontSize: 11, color: '#1677ff' }}>正在处理...</Text>
                        }
                      />
                    </List.Item>
                  )}
                />
              </Space>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

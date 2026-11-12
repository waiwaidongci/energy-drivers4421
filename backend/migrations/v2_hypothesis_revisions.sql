-- v2：假设逐版修订与批准快照
-- 由 backend 启动时幂等执行（ensure_revision_schema + create_all + backfill_revisions），此处留档。
ALTER TABLE retrofit_hypotheses ADD COLUMN current_version INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS hypothesis_revisions (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  hypothesis_id INTEGER NOT NULL,
  version INTEGER NOT NULL,
  finding_id INTEGER NOT NULL,
  action VARCHAR(1200) NOT NULL,
  verification VARCHAR(1200) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'draft',
  created_by VARCHAR(160) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL,
  reviewed_by VARCHAR(160) NOT NULL DEFAULT '',
  reviewed_at DATETIME NULL,
  snapshot JSON NULL,
  UNIQUE KEY (hypothesis_id, version),
  FOREIGN KEY (hypothesis_id) REFERENCES retrofit_hypotheses (id),
  FOREIGN KEY (finding_id) REFERENCES driver_findings (id)
);

-- 存量假设各回填一条 v1 版本；已批准的按当时驱动解释与研究指纹生成 snapshot。

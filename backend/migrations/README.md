# Schema v1 → v2

本地启动使用SQLAlchemy metadata创建初始表。自然键：users.email、building_datasets.name、building_days(dataset_id,building_code,day)、model_runs.name、driver_findings(run_id,feature)、retrofit_hypotheses.title、hypothesis_revisions(hypothesis_id,version)。数值测量与解释列使用DOUBLE。

v2（`v2_hypothesis_revisions.sql`）：retrofit_hypotheses增加current_version并发计数，新增hypothesis_revisions逐版存内容、依据finding、修订/审阅人与批准时冻结的快照。启动时由`ensure_revision_schema`幂等补列、`backfill_revisions`为存量假设回填v1（已批准的补快照），空库直接由create_all建全量。

本目录用于后续版本迁移；更后面的真实升级应编写版本化DDL与回滚步骤，不能仅依赖create_all修改现有列。

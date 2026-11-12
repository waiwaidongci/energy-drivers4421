<script setup lang="ts">
import {ref,onMounted} from 'vue';
import {useRoute} from 'vue-router';
import {useResearch} from '../stores/research';
import {useAuth} from '../stores/auth';
import {createHypothesis,reviseHypothesis,approveHypothesis,downloadHypothesis,downloadHypothesisVersion} from '../api/hypotheses';
import {useTask} from '../hooks/useTask';
import {features} from '../constants/enums';
import {number,date} from '../utils/format';
import type {Hypothesis} from '../types/domain';
import PageHeading from '../components/common/PageHeading.vue';
import ErrorNotice from '../components/common/ErrorNotice.vue';
import StatusBadge from '../components/common/StatusBadge.vue';
const route=useRoute(),lab=useResearch(),auth=useAuth();
const data=ref({title:'运行排程与计量边界复核',finding_id:Number(route.query.finding)||0,action:'先核对运行排程与计量边界，观察该特征与能耗的关联在建筑现场是否成立。',verification:'安排两周独立现场观察，记录共同变化因素；模型系数与置换重要性不构成因果节能承诺。'});
const {busy,error,perform}=useTask();
const editing=ref(0);
const draft=ref({base_version:0,finding_id:0,action:'',verification:''});
onMounted(()=>perform(async()=>{await lab.load();if(!data.value.finding_id)data.value.finding_id=lab.findings[0]?.id||0;}));
const findingOf=(id:number)=>lab.findings.find(f=>f.id===id);
function submit(){perform(async()=>{await createHypothesis(data.value);await lab.load();data.value.title='';});}
function startEdit(h:Hypothesis){const last=h.revisions[0];editing.value=h.id;draft.value={base_version:h.current_version,finding_id:last?.finding_id??h.finding_id,action:last?.action??h.action,verification:last?.verification??h.verification};}
function submitRevision(h:Hypothesis){perform(async()=>{try{await reviseHypothesis(h.id,draft.value);editing.value=0;}finally{await lab.load();}if(editing.value){const fresh=lab.hypotheses.find(x=>x.id===h.id);if(fresh)draft.value.base_version=fresh.current_version;}});}
function approve(id:number,version:number){perform(async()=>{try{await approveHypothesis(id,version);}finally{await lab.load();}});}
</script>
<template>
<PageHeading index="05" title="把关联线索，写成现场可验证的问题" text="分析员提出并逐版修订改造假设，工程负责人逐版审阅；批准版冻结当时的方案、解释数值与研究指纹。未做因果识别，不报告自动节能收益。"/>
<ErrorNotice :message="error" @retry="perform(lab.load)"/>
<div class="hypothesis-layout" :class="{readonly:!auth.canEdit}">
<form v-if="auth.canEdit" class="research-form" @submit.prevent="submit">
<h2>新的现场验证假设</h2>
<label>假设标题<input v-model="data.title" required minlength="2"></label>
<label>依据驱动解释<select v-model="data.finding_id"><option v-for="f in lab.findings" :key="f.id" :value="f.id">研究#{{f.run_id}} / {{features[f.feature]}} / ΔMAE {{number(f.importance_mean,2)}}</option></select></label>
<label>行动假设<textarea v-model="data.action" rows="5" minlength="10" required></textarea></label>
<label>独立验证与解释限制<textarea v-model="data.verification" rows="5" minlength="10" required></textarea></label>
<button class="primary" :disabled="busy||!data.finding_id">保存待审阅假设 →</button>
</form>
<section class="hypothesis-files">
<article v-for="h in lab.hypotheses" :key="h.id">
<div class="file-heading"><p class="eyebrow">RETROFIT HYPOTHESIS / {{String(h.id).padStart(3,'0')}} · 共 {{h.current_version}} 版</p><StatusBadge :status="h.status"/></div>
<h2>{{h.title}}</h2>
<div class="version-list">
<section v-for="r in h.revisions" :key="r.id" class="version-item">
<div class="version-heading"><b>第 {{r.version}} 版</b><StatusBadge :status="r.status"/><small>修订 {{r.created_by||'早期稿件'}} · {{date(r.created_at)}}</small></div>
<p class="finding-link">{{features[findingOf(r.finding_id)?.feature||'']}}<span>研究#{{findingOf(r.finding_id)?.run_id}} · ΔMAE {{number(findingOf(r.finding_id)?.importance_mean,2)}}</span></p>
<h3>行动假设</h3>
<p class="version-text">{{r.action}}</p>
<h3>验证与限制</h3>
<p class="version-text">{{r.verification}}</p>
<footer>
<template v-if="r.status==='approved'">
<small>审阅人 {{r.reviewed_by}}<template v-if="r.reviewed_at"> · {{date(r.reviewed_at)}}</template></small>
<button class="text-button" :disabled="busy" @click="perform(()=>downloadHypothesisVersion(h.id,r.version))">下载第 {{r.version}} 版 CSV ↓</button>
</template>
<template v-else>
<small>等待工程负责人审阅</small>
<button v-if="auth.user?.role==='admin'&&r.version===h.current_version" class="outline" :disabled="busy" @click="approve(h.id,r.version)">审阅并批准第 {{r.version}} 版 ✓</button>
</template>
</footer>
<p v-if="r.snapshot" class="fingerprint">批准时冻结 · 输入指纹 {{r.snapshot.model_input_fingerprint.slice(0,16)}}… · 选择指纹 {{r.snapshot.selection_fingerprint.slice(0,16)}}…</p>
</section>
</div>
<div class="hypothesis-actions">
<button v-if="auth.canEdit" class="outline" :disabled="busy" @click="startEdit(h)">基于第 {{h.current_version}} 版改稿 →</button>
<button v-if="h.status==='approved'" class="text-button" :disabled="busy" @click="perform(()=>downloadHypothesis(h.id))">下载最新批准版 CSV ↓</button>
</div>
<form v-if="editing===h.id" class="research-form revision-form" @submit.prevent="submitRevision(h)">
<h2>修订稿 · 基于第 {{draft.base_version}} 版</h2>
<label>依据驱动解释<select v-model="draft.finding_id"><option v-for="f in lab.findings" :key="f.id" :value="f.id">研究#{{f.run_id}} / {{features[f.feature]}} / ΔMAE {{number(f.importance_mean,2)}}</option></select></label>
<label>行动假设<textarea v-model="draft.action" rows="5" minlength="10" required></textarea></label>
<label>独立验证与解释限制<textarea v-model="draft.verification" rows="5" minlength="10" required></textarea></label>
<button class="primary" :disabled="busy||!draft.finding_id">提交第 {{h.current_version+1}} 版待审阅 →</button>
<button type="button" class="text-button" @click="editing=0">取消改稿</button>
</form>
</article>
<p v-if="!lab.hypotheses.length" class="muted">先完成模型研究，再从一个驱动解释提出现场验证假设。</p>
</section>
</div>
</template>

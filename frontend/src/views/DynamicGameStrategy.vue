<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h2>投标报价决策中心</h2>
        <p>融合投标策略、公司成本调整、竞争推演、规则导入和开标回测。</p>
      </div>
      <button class="primary" :disabled="!selectedRule || loading" @click="runGame">
        <Play :size="17" />{{ loading ? '推演中' : '运行竞争推演' }}
      </button>
    </div>

    <section v-if="loading" class="panel progress-panel">
      <div class="section-head compact-section-head">
        <div>
          <h3>{{ progressLabel }}</h3>
          <p class="field-hint">正在按当前公司成本调整、评分规则和竞争者画像测算报价区间。</p>
        </div>
        <strong>{{ progressPct }}%</strong>
      </div>
      <div class="progress-track">
        <div class="progress-fill" :style="{ width: `${progressPct}%` }" />
      </div>
    </section>

    <section class="panel cost-source-panel">
      <div class="section-head">
        <div>
          <h3>计价批次成本来源</h3>
          <p class="field-hint">报价决策成本线可来自计价批次成本合计，也可读取单项反推后的当前目标合计作为成本线 C。</p>
        </div>
        <div class="header-actions">
          <RouterLink class="secondary" :to="reversePricingRoute">进入单项报价反推</RouterLink>
          <button class="secondary" @click="readSyncedCost">读取单项反推成本线</button>
          <button class="secondary" :disabled="!selectedPricingRun" @click="loadPricingRunAsCost">刷新批次成本</button>
        </div>
      </div>

      <div class="cost-source-layout">
        <aside class="cost-source-status">
          <span class="source-badge" data-mode="batch">计价批次成本</span>
          <strong>{{ costSourceTitle }}</strong>
          <small>{{ syncedCostContext?.syncedAt ? `同步时间：${syncedCostContext.syncedAt}` : '尚未读取成本线。可先选择计价批次，或从单项反推页同步当前成本线。' }}</small>
        </aside>

        <div class="cost-source-controls">
          <div class="form-grid">
            <label>快速查找批次
              <input v-model="pricingRunKeyword" placeholder="输入项目名或批次号" />
            </label>
            <label>计价批次
              <select v-model="selectedPricingRun" @change="loadPricingRunAsCost">
                <option value="">选择批次</option>
                <option v-for="run in filteredPricingRuns" :key="run.run_code" :value="run.run_code">
                  {{ run.project_name || run.run_code }} / {{ run.item_count }} 项
                </option>
              </select>
            </label>
          </div>
          <div class="quick-run-grid">
            <button
              v-for="run in quickPricingRuns"
              :key="run.run_code"
              class="quick-run-card"
              :class="{ selected: selectedPricingRun === run.run_code }"
              @click="selectPricingRun(run.run_code)"
            >
              <strong>{{ run.project_name || run.run_code }}</strong>
              <span>{{ run.item_count }} 项</span>
            </button>
          </div>
          <p class="source-note">
            {{ syncedCostMessage || '读取单项反推成本线：从浏览器本地同步最近一次单项反推页面保存的当前目标合计、批次号和项目数，并作为报价决策成本线 C。' }}
          </p>
        </div>

        <div class="cost-source-metrics">
          <article>
            <span>来源成本合计</span>
            <strong>{{ money(sourceCostTotal) }}</strong>
          </article>
          <article>
            <span>原始成本</span>
            <strong>{{ money(syncedCostContext?.originalCostTotal || sourceCostTotal) }}</strong>
          </article>
          <article>
            <span>调整差额</span>
            <strong>{{ money(syncedCostContext?.adjustmentDelta || 0) }}</strong>
          </article>
          <article>
            <span>来源项目数</span>
            <strong>{{ sourceItemCount || '-' }}</strong>
          </article>
        </div>
      </div>

      <div v-if="reverseItems.length" class="source-list-block">
        <div class="section-head compact-section-head">
          <div>
            <h3>批次清单明细</h3>
            <p class="field-hint">
              共 {{ reverseItems.length }} 项，当前筛选 {{ filteredReverseItems.length }} 项；
              批次总价 {{ money(reverseItemsTotal) }}，筛选合计 {{ money(filteredReverseItemsTotal) }}。
            </p>
          </div>
          <div class="header-actions">
            <button class="secondary" @click="reverseListCollapsed = !reverseListCollapsed">
              {{ reverseListCollapsed ? '展开明细' : '折叠明细' }}
            </button>
            <input v-model="reverseItemKeyword" class="compact-search" placeholder="搜索清单项" @input="reverseItemPage = 1" />
            <select v-model.number="reverseItemPageSize" class="compact-select" @change="reverseItemPage = 1">
              <option :value="10">10 条/页</option>
              <option :value="20">20 条/页</option>
              <option :value="50">50 条/页</option>
            </select>
          </div>
        </div>
        <div v-if="!reverseListCollapsed" class="compact-table-wrap mini-reverse-wrap">
          <table>
            <thead>
              <tr>
                <th>清单项</th>
                <th>工程量</th>
                <th>成本单价</th>
                <th>成本合价</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in pagedReverseItems" :key="item.itemKey">
                <td>{{ item.itemName }}</td>
                <td>{{ item.quantity }}</td>
                <td>{{ money(item.costUnitPrice) }}</td>
                <td>{{ money(item.costTotal) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!reverseListCollapsed" class="pagination-bar">
          <span>第 {{ reverseItemPage }} / {{ reverseItemPageCount }} 页</span>
          <div class="header-actions">
            <button class="secondary" :disabled="reverseItemPage <= 1" @click="reverseItemPage -= 1">上一页</button>
            <button class="secondary" :disabled="reverseItemPage >= reverseItemPageCount" @click="reverseItemPage += 1">下一页</button>
          </div>
        </div>
      </div>
    </section>

    <div class="strategy-grid">
      <section class="panel">
        <div class="section-head">
          <div>
            <h3>报价输入</h3>
            <p class="field-hint">成本搜索调整按公司分别维护，选中公司后用于生成搜索下限。</p>
          </div>
          <div class="header-actions">
            <button class="secondary" @click="quoteInputCollapsed = !quoteInputCollapsed">
              {{ quoteInputCollapsed ? '展开报价输入' : '折叠报价输入' }}
            </button>
            <button class="secondary" @click="fillSample">填入示例</button>
          </div>
        </div>
        <div v-if="quoteInputCollapsed" class="collapsed-summary">
          <span>规则：{{ selectedRule?.name || '-' }}</span>
          <span>公司：{{ selectedCompany?.name || '-' }}</span>
          <span>成本线：{{ money(form.floor) }}</span>
          <span>最高限价：{{ money(form.ceiling) }}</span>
        </div>
        <div v-else class="form-grid">
          <label>评分规则
            <select v-model="selectedRuleId">
              <option v-for="rule in confirmedRules" :key="rule.id" :value="rule.id">{{ rule.name }}</option>
            </select>
          </label>
          <label>公司
            <select v-model="selectedCompanyId">
              <option v-for="company in companyAdjustments" :key="company.id" :value="company.id">{{ company.name }}</option>
            </select>
          </label>
          <label>成本线 C<input v-model="form.floor" /></label>
          <label>公司成本搜索调整 %
            <input v-model="selectedCompany.adjustmentPct" type="number" step="0.1" />
          </label>
          <label>搜索下限<input :value="money(searchFloor)" readonly /></label>
          <label>最高限价 H<input v-model="form.ceiling" /></label>
          <label>搜索步长<input v-model="form.step" /></label>
          <label>小数精度<input v-model.number="form.precision" type="number" min="0" max="6" /></label>
          <label>市场合理均价 μ<input v-model="form.marketMean" placeholder="留空按 85%/90%/95% 自动场景" /></label>
          <label>报价离散程度 σ<input v-model="form.sigma" /></label>
          <label>投标人数模式
            <select v-model="form.bidderMode">
              <option value="range">范围随机</option>
              <option value="fixed">固定人数</option>
            </select>
          </label>
          <label>固定总人数 n<input v-model.number="form.bidderCount" type="number" min="3" @change="normalizeBidderInputs" /></label>
          <label>最少总人数 n_min<input v-model.number="form.bidderMin" type="number" min="3" @change="normalizeBidderInputs" /></label>
          <label>最多总人数 n_max<input v-model.number="form.bidderMax" type="number" min="3" @change="normalizeBidderInputs" /></label>
          <label>模拟次数 N
            <input v-model.number="form.rounds" type="number" min="100" @input="roundsAuto = false" />
            <small class="field-hint">{{ roundsAuto ? `自动推荐：${recommendedRounds} 次` : `手动设置；建议 ${recommendedRounds} 次` }}</small>
          </label>
        </div>
        <div v-if="!quoteInputCollapsed" class="header-actions parameter-actions">
          <button class="secondary" @click="applyRecommendedRounds">使用推荐模拟次数</button>
          <button class="secondary" @click="roundsAuto = !roundsAuto">{{ roundsAuto ? '改为手动 N' : '恢复自动 N' }}</button>
        </div>
      </section>

      <section class="panel">
        <div class="section-head">
          <div>
            <h3>公司成本调整</h3>
            <p class="field-hint">华能、大唐等公司可分别设定成本下探或保留比例。</p>
          </div>
          <div class="header-actions">
            <button class="secondary" @click="companyAdjustCollapsed = !companyAdjustCollapsed">
              {{ companyAdjustCollapsed ? '展开公司调整' : '折叠公司调整' }}
            </button>
            <button class="secondary" @click="addCompany">新增公司</button>
          </div>
        </div>
        <div v-if="companyAdjustCollapsed" class="collapsed-summary">
          <span>当前公司：{{ selectedCompany?.name || '-' }}</span>
          <span>成本搜索调整：{{ selectedCompany?.adjustmentPct || 0 }}%</span>
          <span>搜索下限：{{ money(searchFloor) }}</span>
        </div>
        <table v-else>
          <thead>
            <tr>
              <th>公司</th>
              <th>成本搜索调整 %</th>
              <th>搜索下限</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="company in companyAdjustments" :key="company.id">
              <td><input v-model="company.name" /></td>
              <td><input v-model="company.adjustmentPct" type="number" step="0.1" /></td>
              <td>{{ money(companySearchFloor(company)) }}</td>
              <td>
                <div class="table-actions">
                  <button class="small-action" @click="selectedCompanyId = company.id">使用</button>
                  <button
                    class="small-action danger"
                    :disabled="companyAdjustments.length <= 1"
                    @click="removeCompany(company.id)"
                  >
                    删除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>

    <section class="panel">
      <div class="section-head">
        <div>
          <h3>竞争者画像</h3>
          <p class="field-hint">均值系数以最高限价 H 为基准，概率会自动归一化。</p>
        </div>
        <div class="header-actions">
          <button class="secondary" @click="showProfileHelp = !showProfileHelp">{{ showProfileHelp ? '收起说明' : '查看说明' }}</button>
          <button class="secondary" @click="addProfile">新增画像</button>
        </div>
      </div>
      <section v-if="showProfileHelp" class="profile-help">
        <div>
          <h4>竞争者画像的作用</h4>
          <p>画像不是录入具体公司名称，而是把可能参标单位按报价习惯分组。系统会按这些画像生成对手报价，用来判断我方报价在不同竞争环境下的得分、胜率和利润空间。</p>
          <div class="profile-guide-list">
            <article>
              <strong>低价抢分型</strong>
              <span>代表价格压力大的竞争者。占比越高，系统会认为对手更可能压价，推荐报价会更谨慎。</span>
            </article>
            <article>
              <strong>稳健中位型</strong>
              <span>代表市场常规报价水平。适合作为默认基准，用于没有明确竞争情报时的常规测算。</span>
            </article>
            <article>
              <strong>利润优先型</strong>
              <span>代表更重视利润或项目门槛较高的竞争者。占比越高，推荐区间通常会向利润侧上移。</span>
            </article>
          </div>
        </div>
        <div>
          <h4>参数怎么调</h4>
          <div class="profile-param-grid">
            <p><strong>均值系数</strong><span>对手平均报价位置。调低表示对手更激进，调高表示对手报价更保守。</span></p>
            <p><strong>离散系数</strong><span>对手报价分散程度。调高表示报价不确定性更大，推荐区间会更宽。</span></p>
            <p><strong>概率</strong><span>这类对手出现的可能性。数值越大，这类画像对推荐结果影响越大。</span></p>
            <p><strong>下限/上限</strong><span>对手报价边界。用于约束异常低价或异常高价，避免模拟结果失真。</span></p>
          </div>
          <h4 class="profile-help-subtitle">不会判断时</h4>
          <div class="header-actions profile-presets">
            <button class="secondary" @click="applyProfilePreset('aggressive')">低价激烈</button>
            <button class="secondary" @click="applyProfilePreset('normal')">常规竞争</button>
            <button class="secondary" @click="applyProfilePreset('profit')">利润温和</button>
          </div>
          <p class="field-hint">没有历史数据时先用“常规竞争”。已知华能、大唐等单位压价明显时选“低价激烈”。技术门槛高、参标单位少、报价纪律强时选“利润温和”。开标后可用“开标后回测与校准”反推下一次的画像参数。</p>
        </div>
      </section>
      <table>
        <thead>
          <tr>
            <th>画像</th>
            <th>均值系数</th>
            <th>离散系数</th>
            <th>概率</th>
            <th>下限</th>
            <th>上限</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(profile, index) in profiles" :key="index">
            <td><input v-model="profile.name" /></td>
            <td><input v-model="profile.meanFactor" /></td>
            <td><input v-model="profile.sigmaFactor" /></td>
            <td><input v-model="profile.probability" /></td>
            <td><input v-model="profile.minFactor" /></td>
            <td><input v-model="profile.maxFactor" /></td>
            <td><button class="small-action" @click="profiles.splice(index, 1)">删除</button></td>
          </tr>
        </tbody>
      </table>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="message" class="success">{{ message }}</p>

    <section v-if="result" class="panel">
      <div class="section-head">
        <div>
          <h3>决策结论</h3>
          <p class="field-hint">综合评分表现、胜率稳定性和利润空间形成推荐报价与报价区间。</p>
        </div>
        <div class="header-actions">
          <select v-model="recommendationMode" class="compact-select">
            <option value="balanced">均衡推荐</option>
            <option value="conservative">保守推荐</option>
            <option value="profit">利润优先</option>
          </select>
          <button class="secondary" @click="pushRecommendationToReverse">同步推荐到单项反推</button>
        </div>
      </div>
      <section v-if="recommendation.boundaryWarning" class="attention-panel compact-attention">
        <div>
          <strong>推荐价位于区间边缘</strong>
          <p>{{ recommendation.boundaryWarning }}</p>
        </div>
      </section>
      <div class="result-strip">
        <div><strong>{{ money(recommendation.recommendedBid) }}</strong><span>推荐报价</span></div>
        <div><strong>{{ money(recommendation.intervalLow) }} - {{ money(recommendation.intervalHigh) }}</strong><span>稳健报价区间</span></div>
        <div><strong>{{ number(recommendation.score) }}</strong><span>推荐得分</span></div>
        <div><strong>{{ percent(recommendation.winProbability) }}</strong><span>推荐胜率</span></div>
        <div><strong>{{ money(recommendation.expectedProfit) }}</strong><span>推荐期望利润</span></div>
      </div>
      <div class="recommendation-grid">
        <article class="recommendation-card" :class="{ selected: recommendationMode === 'conservative' }" @click="recommendationMode = 'conservative'">
          <span>保守报价</span>
          <strong>{{ money(recommendation.intervalLow) }}</strong>
          <small>适合防守低价冲击。</small>
        </article>
        <article class="recommendation-card" :class="{ selected: recommendationMode === 'balanced' }" @click="recommendationMode = 'balanced'">
          <span>均衡报价</span>
          <strong>{{ money(recommendation.balancedBid) }}</strong>
          <small>接近稳健区间中位。</small>
        </article>
        <article class="recommendation-card" :class="{ selected: recommendationMode === 'profit' }" @click="recommendationMode = 'profit'">
          <span>利润优先报价</span>
          <strong>{{ money(recommendation.profitBid) }}</strong>
          <small>{{ selectedCompany.name }}，成本调整 {{ selectedCompany.adjustmentPct }}%。</small>
        </article>
      </div>
      <div class="interval-band">
        <div class="interval-band-fill" :style="{ left: `${recommendation.intervalStartPct}%`, width: `${recommendation.intervalWidthPct}%` }" />
        <div class="interval-band-marker" :style="{ left: `${recommendation.recommendedPct}%` }" />
      </div>
      <div class="strategy-chart">
        <div
          v-for="point in chartPoints"
          :key="point.bid"
          class="chart-bar"
          :class="{ best: Number(point.bid) === Number(recommendation.recommendedBid), robust: point.winProbability >= 0.5 }"
          :style="{ height: `${point.height}%` }"
          :title="`${money(point.bid)} / ${number(point.score)} / ${percent(point.winProbability)}`"
        />
      </div>
      <div class="section-head compact-section-head">
        <div>
          <h3>关键报价点</h3>
          <p class="field-hint">默认展示区间、推荐点和邻近报价，完整数据可切换查看。</p>
        </div>
        <select v-model="pointTableMode" class="compact-select">
          <option value="key">关键点</option>
          <option value="robust">稳健区间</option>
          <option value="all">全部报价</option>
        </select>
      </div>
      <div class="compact-table-wrap">
        <table>
          <thead>
            <tr>
              <th>报价</th>
              <th>平均得分</th>
              <th>胜率</th>
              <th>平均基准价</th>
              <th>期望利润</th>
              <th>结果</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="point in visiblePoints" :key="point.bid" :class="{ selected: Number(point.bid) === Number(recommendation.recommendedBid) }">
              <td>{{ money(point.bid) }}</td>
              <td>{{ number(point.score) }}</td>
              <td>{{ percent(point.winProbability) }}</td>
              <td>{{ money(point.benchmark) }}</td>
              <td>{{ money(point.expectedProfit) }}</td>
              <td>{{ pointLabel(point) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div class="strategy-grid">
      <section class="panel">
        <div class="section-head">
          <div>
            <h3>规则文件导入</h3>
            <p class="field-hint">解析图片、PDF、Word、TXT 为规则草稿，复核后保存到规则库。</p>
          </div>
          <button class="secondary" @click="loadRuleFiles">刷新文件</button>
        </div>
        <div class="form-grid">
          <label>规则文件
            <select v-model="selectedRuleFile">
              <option value="">选择规则文件</option>
              <option v-for="file in ruleFiles" :key="file.path" :value="file.path">{{ file.name }} ({{ file.extension }})</option>
            </select>
          </label>
        </div>
        <div class="header-actions rule-import-actions">
          <button class="secondary" :disabled="!selectedRuleFile || parsingRule" @click="parseSelectedRuleFile(false)">
            {{ parsingRule ? '生成中...' : '快速生成草稿' }}
          </button>
          <button class="secondary" :disabled="!selectedRuleFile || parsingRule" @click="parseSelectedRuleFile(true)">
            深度OCR解析
          </button>
          <button class="secondary" :disabled="!draftRuleJson || savingParsedRule" @click="saveParsedRule">
            {{ savingParsedRule ? '保存中...' : '确认保存规则' }}
          </button>
        </div>
        <div class="rule-import-help">
          <strong>建议先用快速生成草稿。</strong>
          <span>快速模式会跳过图片/扫描件 OCR，先生成可编辑规则模板，适合马上复核并保存；只有当文件必须识别图片文字时，再使用深度 OCR 解析。</span>
        </div>
        <div v-if="parsingRule || parseStatus !== 'idle' || parseError" class="rule-import-status" :data-state="parseError ? 'error' : parseStatus === 'success' ? 'success' : 'running'">
          <div class="section-head compact-section-head">
            <div>
              <strong>{{ parseStatusTitle }}</strong>
              <p class="field-hint">{{ parseStatusText }}</p>
            </div>
            <span>{{ parseProgress }}%</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" :style="{ width: `${parseProgress}%` }" />
          </div>
        </div>
        <label class="stacked-label">识别文本<textarea v-model="extractedText" class="small-textarea" spellcheck="false" /></label>
        <label class="stacked-label">规则草稿 JSON<textarea v-model="draftRuleJson" class="json-textarea" spellcheck="false" /></label>
      </section>

      <section class="panel">
        <div class="section-head">
          <div>
            <h3>开标后回测与校准</h3>
            <p class="field-hint">复算基准价、得分和排名，并可反推 μ、σ、n 用于下次模拟。</p>
          </div>
        </div>
        <label class="stacked-label">已开标总报价<textarea v-model="actualBids" class="small-textarea" spellcheck="false" /></label>
        <div class="header-actions">
          <button class="secondary" :disabled="!selectedRule || !actualBids" @click="runBacktest">按当前规则复算</button>
          <button class="secondary" :disabled="!selectedRule || !actualBids" @click="calibrateFromActualBids">用开标数据校准</button>
          <button class="secondary" :disabled="!backtestRows.length" @click="exportBacktestExcel">导出Excel</button>
        </div>
        <p v-if="backtestRows.length" class="field-hint">
          距第一名分差表示该单位得分与第 1 名得分的差值；距第一名报价差表示该单位报价与第 1 名报价的金额差。
        </p>
        <table v-if="backtestRows.length">
          <thead>
            <tr>
              <th>排名</th>
              <th>单位</th>
              <th>报价</th>
              <th>基准价</th>
              <th>得分</th>
              <th>距第一名分差</th>
              <th>距第一名报价差</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in backtestRows" :key="`${row.rank}-${row.name}`">
              <td>{{ row.rank }}</td>
              <td>{{ row.name }}</td>
              <td>{{ money(row.amount) }}</td>
              <td>{{ money(row.benchmark) }}</td>
              <td>{{ number(row.rankScore) }}</td>
              <td>{{ number(row.gapToFirstScore) }} 分</td>
              <td>{{ money(row.gapToFirstAmount) }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>

    <section class="panel">
      <div class="section-head">
        <div>
          <h3>规则库</h3>
          <p class="field-hint">已确认规则会进入报价计算下拉框，草稿规则可继续复核。</p>
        </div>
      </div>
      <div class="recommendation-grid">
        <article v-for="rule in rules" :key="rule.id" class="recommendation-card">
          <span>{{ rule.status === 'draft' ? '草稿' : '已确认' }}</span>
          <strong>{{ rule.name }}</strong>
          <small>{{ rule.source || '规则库' }}；满分 {{ rule.maxScore || 100 }}</small>
        </article>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { Play } from '@lucide/vue'
import { api } from '../api/client'

interface BidRule { id: string; name: string; status?: string; source?: string; maxScore?: number }
interface CompanyAdjustment { id: string; name: string; adjustmentPct: string }
interface RuleFile { name: string; extension: string; path: string }
interface PricingRun { run_code: string; project_name: string | null; item_count: number }
interface ReverseCostItem {
  itemKey: string
  itemName: string
  quantity: string
  costUnitPrice: string
  costTotal: string
}
interface CostSyncContext {
  source?: string
  runCode?: string
  originalCostTotal?: string
  adjustedCostLine?: string
  adjustmentDelta?: string
  targetTotal?: string
  costLine?: string
  itemCount?: number
  autoRunGame?: boolean
  syncId?: string
  syncedAt?: string
}
interface UnifiedPoint {
  bid: string | number
  score: number
  benchmark: string | number
  winProbability: number
  expectedProfit: string | number
  robust?: boolean
}
interface UnifiedResult {
  points: UnifiedPoint[]
  best: UnifiedPoint
  interval?: { low?: UnifiedPoint; balanced?: UnifiedPoint; high?: UnifiedPoint; recommended?: UnifiedPoint; count?: number }
  summary?: { floor?: string; ceiling?: string; step?: string; rounds?: number }
}

const rules = ref<BidRule[]>([])
const ruleFiles = ref<RuleFile[]>([])
const pricingRuns = ref<PricingRun[]>([])
const selectedRuleId = ref('')
const selectedRuleFile = ref('')
const selectedPricingRun = ref('')
const pricingRunKeyword = ref('')
const loading = ref(false)
const parsingRule = ref(false)
const savingParsedRule = ref(false)
const roundsAuto = ref(true)
const error = ref('')
const message = ref('')
const progressPct = ref(0)
const progressLabel = ref('准备计算')
const parseProgress = ref(0)
const parseStatus = ref<'idle' | 'running' | 'success' | 'error'>('idle')
const parseStatusText = ref('请选择规则文件后开始解析。')
const parseError = ref('')
const result = ref<UnifiedResult | null>(null)
const syncedCostContext = ref<CostSyncContext | null>(null)
const syncedCostMessage = ref('')
const lastAutoRunSyncId = ref('')
const extractedText = ref('')
const draftRuleJson = ref('')
const actualBids = ref('')
const backtestRows = ref<any[]>([])
const reverseItems = ref<ReverseCostItem[]>([])
const reverseItemKeyword = ref('')
const reverseItemPage = ref(1)
const reverseItemPageSize = ref(20)
const reverseListCollapsed = ref(true)
const showProfileHelp = ref(false)
const quoteInputCollapsed = ref(false)
const companyAdjustCollapsed = ref(false)
const selectedCompanyId = ref('huawei-energy')
const recommendationMode = ref<'balanced' | 'conservative' | 'profit'>('balanced')
const pointTableMode = ref<'key' | 'robust' | 'all'>('key')

const form = reactive({
  floor: '8500000',
  ceiling: '10000000',
  step: '50000',
  precision: 3,
  marketMean: '',
  sigma: '500000',
  bidderMode: 'range',
  bidderCount: 8,
  bidderMin: 3,
  bidderMax: 12,
  rounds: 500
})
const companyAdjustments = reactive<CompanyAdjustment[]>([
  { id: 'huawei-energy', name: '华能', adjustmentPct: '-5' },
  { id: 'datang', name: '大唐', adjustmentPct: '-3' },
  { id: 'huadian', name: '华电', adjustmentPct: '-4' },
  { id: 'guodian', name: '国家能源', adjustmentPct: '-2' }
])
const profiles = reactive([
  { name: '低价抢分型', meanFactor: '0.86', sigmaFactor: '0.025', probability: '0.35', minFactor: '0.78', maxFactor: '0.92' },
  { name: '稳健中位型', meanFactor: '0.91', sigmaFactor: '0.030', probability: '0.45', minFactor: '0.84', maxFactor: '0.97' },
  { name: '利润优先型', meanFactor: '0.95', sigmaFactor: '0.020', probability: '0.20', minFactor: '0.90', maxFactor: '1.00' }
])
let progressTimer: ReturnType<typeof window.setInterval> | undefined
let parseProgressTimer: ReturnType<typeof window.setInterval> | undefined

const confirmedRules = computed(() => rules.value.filter(rule => rule.status !== 'draft'))
const selectedRule = computed(() => confirmedRules.value.find(rule => rule.id === selectedRuleId.value))
const parseStatusTitle = computed(() => {
  if (parseStatus.value === 'success') return '规则草稿已生成'
  if (parseStatus.value === 'error') return '规则解析失败'
  if (parsingRule.value) return '正在解析规则文件'
  return '规则解析'
})
const selectedCompany = computed(() => companyAdjustments.find(company => company.id === selectedCompanyId.value) || companyAdjustments[0])
const searchFloor = computed(() => companySearchFloor(selectedCompany.value))
const sourceCostTotal = computed(() => Number(syncedCostContext.value?.costLine || form.floor || 0))
const sourceItemCount = computed(() => syncedCostContext.value?.itemCount || reverseItems.value.length || 0)
const candidateCount = computed(() => {
  const step = Math.max(1, Number(form.step || 1))
  return Math.max(1, Math.floor((Number(form.ceiling || 0) - searchFloor.value) / step) + 1)
})
const recommendedRounds = computed(() => {
  const biddersSpan = form.bidderMode === 'fixed'
    ? 1
    : Math.max(1, Number(form.bidderMax || 3) - Number(form.bidderMin || 3) + 1)
  const candidateLoad = candidateCount.value <= 80 ? 1.25 : candidateCount.value <= 180 ? 1 : 0.75
  const bidderLoad = biddersSpan <= 4 ? 1 : biddersSpan <= 8 ? 1.15 : 1.3
  const value = Math.round((700 * candidateLoad * bidderLoad) / 50) * 50
  return Math.max(300, Math.min(3000, value))
})
const filteredPricingRuns = computed(() => {
  const keyword = pricingRunKeyword.value.trim().toLowerCase()
  if (!keyword) return pricingRuns.value
  return pricingRuns.value.filter(run =>
    (run.project_name || '').toLowerCase().includes(keyword) ||
    run.run_code.toLowerCase().includes(keyword)
  )
})
const quickPricingRuns = computed(() => {
  const selected = selectedPricingRun.value
    ? pricingRuns.value.filter(run => run.run_code === selectedPricingRun.value)
    : []
  const merged = [...selected, ...filteredPricingRuns.value]
  const seen = new Set<string>()
  return merged.filter(run => {
    if (seen.has(run.run_code)) return false
    seen.add(run.run_code)
    return true
  }).slice(0, 4)
})
const filteredReverseItems = computed(() => {
  const keyword = reverseItemKeyword.value.trim().toLowerCase()
  if (!keyword) return reverseItems.value
  return reverseItems.value.filter(item =>
    item.itemName.toLowerCase().includes(keyword) ||
    item.itemKey.toLowerCase().includes(keyword)
  )
})
const reverseItemsTotal = computed(() => reverseItems.value.reduce((sum, item) => sum + Number(item.costTotal || 0), 0))
const filteredReverseItemsTotal = computed(() => filteredReverseItems.value.reduce((sum, item) => sum + Number(item.costTotal || 0), 0))
const reverseItemPageCount = computed(() => Math.max(1, Math.ceil(filteredReverseItems.value.length / reverseItemPageSize.value)))
const pagedReverseItems = computed(() => {
  if (reverseItemPage.value > reverseItemPageCount.value) reverseItemPage.value = reverseItemPageCount.value
  const start = (reverseItemPage.value - 1) * reverseItemPageSize.value
  return filteredReverseItems.value.slice(start, start + reverseItemPageSize.value)
})
const costSourceTitle = computed(() => {
  if (selectedPricingRun.value) {
    const run = pricingRuns.value.find(item => item.run_code === selectedPricingRun.value)
    return run?.project_name || selectedPricingRun.value
  }
  return syncedCostContext.value?.source || '请选择计价批次'
})
const reversePricingRoute = computed(() => ({
  path: '/bid-reverse-pricing',
  query: {
    ...(syncedCostContext.value?.runCode ? { run_code: syncedCostContext.value.runCode } : {}),
    ...(result.value && recommendation.value.recommendedBid !== '0'
      ? { target_total: recommendation.value.recommendedBid }
      : {})
  }
}))
const chartPoints = computed(() => {
  if (!result.value) return []
  const maxScore = Math.max(...result.value.points.map(point => Number(point.score)), 1)
  return result.value.points.map(point => ({ ...point, height: Math.max(4, Number(point.score) / maxScore * 100) }))
})
const recommendation = computed(() => {
  const empty = { recommendedBid: '0', balancedBid: '0', profitBid: '0', intervalLow: '0', intervalHigh: '0', score: 0, winProbability: 0, expectedProfit: '0', intervalStartPct: 0, intervalWidthPct: 0, recommendedPct: 0, boundaryWarning: '' }
  if (!result.value) return empty
  const interval = result.value.interval
  const low = interval?.low || result.value.best
  const high = interval?.high || result.value.best
  const balanced = interval?.balanced || result.value.best
  const profit = interval?.recommended || high
  const recommended = recommendationMode.value === 'conservative'
    ? low
    : recommendationMode.value === 'profit'
      ? profit
      : balanced
  const floor = Number(result.value.summary?.floor || searchFloor.value)
  const ceiling = Number(result.value.summary?.ceiling || form.ceiling)
  const span = Math.max(1, ceiling - floor)
  const lowBid = Number(low.bid)
  const highBid = Number(high.bid)
  const recommendedBid = Number(recommended.bid)
  const intervalCount = Number(interval?.count || 1)
  const isEdge = recommendedBid === lowBid || recommendedBid === highBid
  const boundaryWarning = isEdge
    ? recommendationMode.value === 'profit'
      ? '利润优先报价落在稳健区间上沿，这是为了在满足当前得分和胜率约束时尽量提高收益。建议同时关注均衡报价；若区间点数很少，应调小搜索步长或扩大模拟次数复核。'
      : '当前推荐价落在稳健区间边界，说明可选高分区间较窄。建议调小搜索步长、复核成本搜索调整%，或使用开标数据校准 μ、σ、n 后再运行。'
    : ''
  const startPct = Math.max(0, Math.min(100, ((lowBid - floor) / span) * 100))
  const endPct = Math.max(startPct, Math.min(100, ((highBid - floor) / span) * 100))
  return {
    recommendedBid: String(recommended.bid),
    balancedBid: String(balanced.bid),
    profitBid: String(profit.bid),
    intervalLow: String(low.bid),
    intervalHigh: String(high.bid),
    score: Number(recommended.score),
    winProbability: Number(recommended.winProbability || 0),
    expectedProfit: String(recommended.expectedProfit || 0),
    intervalStartPct: startPct,
    intervalWidthPct: Math.max(1, endPct - startPct),
    recommendedPct: Math.max(0, Math.min(100, ((recommendedBid - floor) / span) * 100)),
    boundaryWarning: intervalCount <= 2 ? boundaryWarning || '稳健区间报价点较少，建议调小搜索步长后复算。' : boundaryWarning
  }
})
const visiblePoints = computed(() => {
  if (!result.value) return []
  if (pointTableMode.value === 'all') return result.value.points
  if (pointTableMode.value === 'robust') return result.value.points.filter(point => point.robust)
  const bids = new Set([
    Number(recommendation.value.intervalLow),
    Number(recommendation.value.balancedBid),
    Number(recommendation.value.profitBid),
    Number(recommendation.value.recommendedBid)
  ])
  result.value.points.forEach((point, index, list) => {
    if (point.robust) bids.add(Number(point.bid))
    const isRecommended = Number(point.bid) === Number(recommendation.value.recommendedBid)
    if (isRecommended) {
      list.slice(Math.max(0, index - 2), Math.min(list.length, index + 3)).forEach(item => bids.add(Number(item.bid)))
    }
  })
  const rows = result.value.points.filter(point => bids.has(Number(point.bid)))
  return rows.length > 18 ? rows.slice(0, 18) : rows
})

function money(value: string | number) {
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 }).format(Number(value || 0))
}

function number(value: string | number) {
  return Number(value || 0).toFixed(form.precision)
}

function percent(value: number) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`
}

function pointLabel(point: UnifiedPoint) {
  const bid = Number(point.bid)
  if (bid === Number(recommendation.value.recommendedBid)) return '当前推荐'
  if (bid === Number(recommendation.value.intervalLow)) return '保守下沿'
  if (bid === Number(recommendation.value.balancedBid)) return '均衡点'
  if (bid === Number(recommendation.value.profitBid)) return '利润优先'
  if (point.robust) return '稳健区间'
  return '-'
}

function companySearchFloor(company: CompanyAdjustment) {
  const base = Number(form.floor || 0)
  const pct = Number(company.adjustmentPct || 0)
  return Math.max(1, Math.round(base * (1 + pct / 100)))
}

function normalizePoint(point: any): UnifiedPoint {
  return {
    bid: point.bid,
    score: Number(point.averageScore ?? point.myScore ?? point.score ?? 0),
    benchmark: point.averageBenchmark ?? point.benchmark ?? 0,
    winProbability: Number(point.winProbability || 0),
    expectedProfit: point.expectedProfit ?? Number(point.bid || 0) - searchFloor.value,
    robust: Boolean(point.robust || point.wins)
  }
}

function normalizeResult(data: any): UnifiedResult {
  const points = (data.points || []).map(normalizePoint)
  const best = normalizePoint(data.best || points[0])
  const interval = data.interval
    ? {
        low: intervalPoint(data.interval.low),
        balanced: intervalPoint(data.interval.balanced),
        high: intervalPoint(data.interval.high),
        recommended: intervalPoint(data.interval.recommended),
        count: data.interval.count
      }
    : buildLocalInterval(points, best)
  return { points, best, interval, summary: { ...(data.summary || {}), floor: String(searchFloor.value), ceiling: form.ceiling, step: form.step, rounds: form.rounds } }
}

function intervalPoint(value: any) {
  return value ? normalizePoint(value) : undefined
}

function buildLocalInterval(points: UnifiedPoint[], best: UnifiedPoint) {
  const bestScore = Math.max(...points.map(point => Number(point.score || 0)), 1)
  const bestWin = Math.max(...points.map(point => Number(point.winProbability || 0)), 0)
  const eligible = points.filter(point => point.score >= bestScore * 0.98 && point.winProbability >= Math.max(0.25, bestWin * 0.75))
  const segment = eligible.length ? eligible : [best]
  const low = segment[0]
  const high = segment[segment.length - 1]
  const balanced = segment[Math.floor(segment.length / 2)]
  return { low, balanced, high, recommended: high, count: segment.length }
}

function addProfile() {
  profiles.push({ name: '新竞争者', meanFactor: '0.90', sigmaFactor: '0.03', probability: '0.10', minFactor: '0.80', maxFactor: '1.00' })
}

function replaceProfiles(values: typeof profiles) {
  profiles.splice(0, profiles.length, ...values)
}

function applyProfilePreset(type: 'aggressive' | 'normal' | 'profit') {
  if (type === 'aggressive') {
    replaceProfiles([
      { name: '低价抢分型', meanFactor: '0.83', sigmaFactor: '0.030', probability: '0.55', minFactor: '0.76', maxFactor: '0.90' },
      { name: '稳健中位型', meanFactor: '0.90', sigmaFactor: '0.025', probability: '0.35', minFactor: '0.84', maxFactor: '0.96' },
      { name: '利润优先型', meanFactor: '0.95', sigmaFactor: '0.020', probability: '0.10', minFactor: '0.90', maxFactor: '1.00' }
    ])
  } else if (type === 'profit') {
    replaceProfiles([
      { name: '低价抢分型', meanFactor: '0.87', sigmaFactor: '0.025', probability: '0.20', minFactor: '0.80', maxFactor: '0.93' },
      { name: '稳健中位型', meanFactor: '0.92', sigmaFactor: '0.025', probability: '0.45', minFactor: '0.86', maxFactor: '0.98' },
      { name: '利润优先型', meanFactor: '0.96', sigmaFactor: '0.018', probability: '0.35', minFactor: '0.91', maxFactor: '1.00' }
    ])
  } else {
    replaceProfiles([
      { name: '低价抢分型', meanFactor: '0.86', sigmaFactor: '0.025', probability: '0.35', minFactor: '0.78', maxFactor: '0.92' },
      { name: '稳健中位型', meanFactor: '0.91', sigmaFactor: '0.030', probability: '0.45', minFactor: '0.84', maxFactor: '0.97' },
      { name: '利润优先型', meanFactor: '0.95', sigmaFactor: '0.020', probability: '0.20', minFactor: '0.90', maxFactor: '1.00' }
    ])
  }
}

function addCompany() {
  const id = `company-${Date.now()}`
  companyAdjustments.push({ id, name: '新公司', adjustmentPct: '0' })
  selectedCompanyId.value = id
}

function removeCompany(id: string) {
  if (companyAdjustments.length <= 1) return
  const index = companyAdjustments.findIndex(company => company.id === id)
  if (index < 0) return
  companyAdjustments.splice(index, 1)
  if (selectedCompanyId.value === id) {
    selectedCompanyId.value = companyAdjustments[Math.min(index, companyAdjustments.length - 1)]?.id || companyAdjustments[0]?.id || ''
  }
}

function fillSample() {
  form.ceiling = '12000000'
  form.floor = '6000000'
  form.step = '10000'
  form.marketMean = ''
  form.sigma = '600000'
  applyRecommendedRounds()
}

async function loadRules(selectedId = '') {
  const { data } = await api.get<BidRule[]>('/bid-strategy/rules')
  rules.value = data
  selectedRuleId.value = selectedId || selectedRuleId.value || confirmedRules.value[0]?.id || data[0]?.id || ''
}

async function loadRuleFiles() {
  const { data } = await api.get<RuleFile[]>('/bid-strategy/rule-files')
  ruleFiles.value = data
  selectedRuleFile.value = selectedRuleFile.value || data[0]?.path || ''
}

async function loadPricingRuns() {
  const { data } = await api.get<PricingRun[]>('/pricing/runs?limit=100')
  pricingRuns.value = data
  if (!selectedPricingRun.value && data[0]?.run_code) {
    selectedPricingRun.value = data[0].run_code
    await loadPricingRunAsCost()
  }
}

async function selectPricingRun(runCode: string) {
  selectedPricingRun.value = runCode
  await loadPricingRunAsCost()
}

async function loadPricingRunAsCost() {
  if (!selectedPricingRun.value) return
  const { data } = await api.get(`/pricing/runs/${selectedPricingRun.value}`)
  const rows = (data.results || []) as Array<{
    source_sheet?: string
    source_row_number?: number
    item_name?: string
    quantity?: string | number | null
    unit_price?: string | number | null
    total_price?: string | number | null
  }>
  reverseItems.value = rows.map(item => {
    const quantity = String(item.quantity || 0)
    const unitPrice = String(item.unit_price || 0)
    const totalPrice = String(item.total_price || Number(quantity) * Number(unitPrice))
    return {
      itemKey: `${item.source_sheet || ''}:${item.source_row_number || ''}`,
      itemName: item.item_name || '',
      quantity,
      costUnitPrice: unitPrice,
      costTotal: Number(totalPrice).toFixed(2)
    }
  })
  reverseItemPage.value = 1
  reverseListCollapsed.value = true
  const total = reverseItems.value.reduce((sum, item) => sum + Number(item.costTotal || 0), 0)
  applyCostSync({
    source: `计价批次 ${selectedPricingRun.value}`,
    runCode: selectedPricingRun.value,
    originalCostTotal: total.toFixed(2),
    adjustedCostLine: total.toFixed(2),
    adjustmentDelta: '0.00',
    costLine: total.toFixed(2),
    targetTotal: total.toFixed(2),
    itemCount: reverseItems.value.length,
    syncedAt: new Date().toLocaleString('zh-CN')
  })
  message.value = `已读取计价批次成本：${money(total)}，共 ${reverseItems.value.length} 项。`
}

function startProgress() {
  progressPct.value = 8
  progressLabel.value = '初始化模拟参数'
  if (progressTimer) window.clearInterval(progressTimer)
  progressTimer = window.setInterval(() => {
    if (!loading.value) return
    if (progressPct.value < 30) progressLabel.value = '生成竞争者报价场景'
    else if (progressPct.value < 65) progressLabel.value = '计算候选报价得分'
    else progressLabel.value = '汇总推荐报价区间'
    progressPct.value = Math.min(92, progressPct.value + Math.max(1, Math.round((100 - progressPct.value) * 0.08)))
  }, 350)
}

function finishProgress() {
  progressPct.value = 100
  progressLabel.value = '计算完成'
  if (progressTimer) {
    window.clearInterval(progressTimer)
    progressTimer = undefined
  }
}

async function runGame() {
  if (!selectedRule.value) return
  normalizeBidderInputs()
  if (roundsAuto.value) applyRecommendedRounds()
  loading.value = true
  startProgress()
  error.value = ''
  message.value = ''
  try {
    const { data } = await api.post('/bid-strategy/simulate', {
      rule: selectedRule.value,
      floor: searchFloor.value,
      ceiling: Number(form.ceiling),
      step: Number(form.step),
      marketMean: form.marketMean ? Number(form.marketMean) : null,
      sigma: Number(form.sigma || 0),
      bidderMode: form.bidderMode,
      bidderCount: form.bidderCount,
      bidderMin: form.bidderMin,
      bidderMax: form.bidderMax,
      simulationCount: form.rounds
    })
    result.value = normalizeResult(data)
    pushRecommendationToReverse()
    message.value = `${selectedCompany.value.name} 成本调整 ${selectedCompany.value.adjustmentPct}%，搜索下限 ${money(searchFloor.value)}，已完成竞争推演。`
    finishProgress()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
    progressLabel.value = '计算失败'
  } finally {
    if (progressTimer) {
      window.clearInterval(progressTimer)
      progressTimer = undefined
    }
    loading.value = false
  }
}

function normalizeBidderInputs() {
  form.bidderCount = Math.max(3, Number(form.bidderCount || 3))
  form.bidderMin = Math.max(3, Number(form.bidderMin || 3))
  form.bidderMax = Math.max(3, Number(form.bidderMax || 3))
  if (form.bidderMax < form.bidderMin) form.bidderMax = form.bidderMin
  if (form.bidderMode === 'fixed') {
    form.bidderMin = form.bidderCount
    form.bidderMax = form.bidderCount
  }
}

function applyRecommendedRounds() {
  form.rounds = recommendedRounds.value
  roundsAuto.value = true
}

function syncRecommendedRoundsIfAuto() {
  if (roundsAuto.value) form.rounds = recommendedRounds.value
}

function pushRecommendationToReverse() {
  if (!result.value) return
  localStorage.setItem('bid_generation_game_recommendation', JSON.stringify({
    syncId: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    source: '报价决策',
    runCode: syncedCostContext.value?.runCode,
    company: selectedCompany.value.name,
    costAdjustmentPct: selectedCompany.value.adjustmentPct,
    originalCostTotal: syncedCostContext.value?.originalCostTotal,
    adjustedCostLine: String(sourceCostTotal.value || form.floor),
    costLine: String(sourceCostTotal.value || form.floor),
    searchFloor: String(searchFloor.value),
    targetTotal: recommendation.value.recommendedBid,
    recommendedBid: recommendation.value.recommendedBid,
    autoApplyReverse: true,
    intervalLow: recommendation.value.intervalLow,
    intervalHigh: recommendation.value.intervalHigh,
    winProbability: recommendation.value.winProbability,
    expectedProfit: recommendation.value.expectedProfit,
    syncedAt: new Date().toLocaleString('zh-CN')
  }))
  message.value = '推荐报价已同步到单项报价反推。'
}

async function parseSelectedRuleFile(allowHeavy = false) {
  if (!selectedRuleFile.value) return
  parsingRule.value = true
  parseStatus.value = 'running'
  parseError.value = ''
  parseProgress.value = 8
  parseStatusText.value = allowHeavy ? '已接收深度 OCR 解析请求，正在读取规则文件。' : '已接收快速生成请求，正在创建可编辑规则草稿。'
  extractedText.value = ''
  draftRuleJson.value = ''
  error.value = ''
  message.value = ''
  startParseProgress(allowHeavy)
  try {
    const { data } = await api.post('/bid-strategy/parse-rule', { path: selectedRuleFile.value, allow_heavy: allowHeavy }, { timeout: allowHeavy ? 300000 : 60000 })
    extractedText.value = data.text || ''
    draftRuleJson.value = JSON.stringify(data.rule, null, 2)
    finishParseProgress(data.modelMessage ? `已生成规则草稿：${data.modelMessage}` : '已生成规则草稿，请复核识别文本和 JSON 后保存。')
    message.value = data.modelMessage ? `已生成规则草稿：${data.modelMessage}` : '已生成规则草稿。'
  } catch (err) {
    const rawText = err instanceof Error ? err.message : String(err)
    const text = rawText.includes('timeout')
      ? '规则文件解析耗时过长，已停止等待。请确认本地 OCR/模型服务是否可用，或换用文字版 PDF、Word、TXT 后重试。'
      : rawText
    parseStatus.value = 'error'
    parseError.value = text
    parseProgress.value = 100
    parseStatusText.value = `解析失败：${text}`
    error.value = text
  } finally {
    stopParseProgress()
    parsingRule.value = false
  }
}

async function saveParsedRule() {
  savingParsedRule.value = true
  error.value = ''
  message.value = ''
  try {
    const rule = JSON.parse(draftRuleJson.value)
    const { data } = await api.post('/bid-strategy/rules', { rule })
    await loadRules(data.id)
    parseStatus.value = 'success'
    parseProgress.value = 100
    parseStatusText.value = `规则 ${data.name || data.id || ''} 已保存并加入计算规则下拉框。`
    message.value = '规则已保存并加入计算规则下拉框。'
  } catch (err) {
    const text = err instanceof Error ? err.message : String(err)
    parseStatus.value = 'error'
    parseError.value = text
    parseStatusText.value = `保存失败：${text}`
    error.value = text
  } finally {
    savingParsedRule.value = false
  }
}

function startParseProgress(allowHeavy = false) {
  stopParseProgress()
  const steps = allowHeavy ? [
    { pct: 18, text: '正在读取文件内容和版面信息。' },
    { pct: 36, text: '正在识别文本并清洗规则描述。' },
    { pct: 58, text: '正在抽取评标规则、分值和计算参数。' },
    { pct: 78, text: '正在生成规则草稿 JSON。' },
    { pct: 90, text: '正在校验草稿结构，请稍候。' },
    { pct: 94, text: '图片或扫描件识别可能较慢，系统仍在处理。' },
    { pct: 96, text: '正在等待解析结果，完成后会自动展示草稿。' }
  ] : [
    { pct: 24, text: '正在读取文件信息。' },
    { pct: 52, text: '正在按默认评标模板生成草稿。' },
    { pct: 82, text: '正在校验草稿结构。' },
    { pct: 94, text: '即将展示规则草稿，请复核后保存。' }
  ]
  let index = 0
  parseProgressTimer = window.setInterval(() => {
    const step = steps[index]
    if (!step) return
    parseProgress.value = Math.max(parseProgress.value, step.pct)
    parseStatusText.value = step.text
    index += 1
  }, allowHeavy ? 900 : 450)
}

function finishParseProgress(text: string) {
  parseStatus.value = 'success'
  parseProgress.value = 100
  parseStatusText.value = text
}

function stopParseProgress() {
  if (parseProgressTimer) {
    window.clearInterval(parseProgressTimer)
    parseProgressTimer = undefined
  }
}

async function runBacktest() {
  if (!selectedRule.value) return
  error.value = ''
  try {
    const { data } = await api.post('/bid-strategy/backtest', { rule: selectedRule.value, actualBids: actualBids.value })
    backtestRows.value = data.rows || []
    message.value = `已复算开标结果，第一名 ${data.winner?.name || '-'}，报价 ${money(data.winner?.amount || 0)}。`
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

function escapeHtml(value: unknown) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function excelCell(value: unknown, text = false) {
  const attrs = text ? ' style="mso-number-format:\\@"' : ''
  return `<td${attrs}>${escapeHtml(value)}</td>`
}

function excelRow(values: unknown[], text = false) {
  return `<tr>${values.map(value => excelCell(value, text)).join('')}</tr>`
}

function downloadBlob(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function exportBacktestExcel() {
  if (!selectedRule.value || !backtestRows.value.length) return
  const exportedAt = new Date().toLocaleString('zh-CN')
  const resultRows = backtestRows.value.map(row => excelRow([
    row.rank,
    row.name,
    row.rawLine || '',
    row.amount,
    row.benchmark,
    row.deviation,
    row.score,
    Number.isFinite(row.weightedScore) ? row.weightedScore : '',
    row.rankScore,
    row.gapToPreviousScore,
    row.gapToPreviousAmount,
    row.gapToFirstScore,
    row.gapToFirstAmount
  ]))
  const ruleJson = JSON.stringify(selectedRule.value, null, 2)
  const html = `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    table { border-collapse: collapse; }
    td, th { border: 1px solid #999; padding: 6px; }
    th { background: #e8f0ec; font-weight: bold; }
  </style>
</head>
<body>
  <h2>开标后回测结果</h2>
  <table>
    ${excelRow(['导出时间', exportedAt], true)}
    ${excelRow(['规则ID', selectedRule.value.id], true)}
    ${excelRow(['规则名称', selectedRule.value.name], true)}
    ${excelRow(['复算评标基准价', backtestRows.value[0]?.benchmark || ''])}
    ${excelRow(['小数精度', form.precision])}
  </table>
  <br>
  <table>
    <tr>
      <th>排名</th>
      <th>投标对象</th>
      <th>原始输入</th>
      <th>投标金额</th>
      <th>基准价</th>
      <th>偏差率</th>
      <th>原始得分</th>
      <th>加权得分</th>
      <th>排名得分</th>
      <th>距上一名分差</th>
      <th>距上一名报价差</th>
      <th>距第一名分差</th>
      <th>距第一名报价差</th>
    </tr>
    ${resultRows.join('\n')}
  </table>
  <br>
  <h2>对应规则JSON</h2>
  <table>
    <tr><th>规则JSON</th></tr>
    <tr><td style="mso-number-format:\\@"><pre>${escapeHtml(ruleJson)}</pre></td></tr>
  </table>
</body>
</html>`
  const safeRuleName = String(selectedRule.value.name || selectedRule.value.id || 'rule').replace(/[\\/:*?"<>|]+/g, '_').slice(0, 40)
  const timestamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14)
  downloadBlob(`开标后回测_${safeRuleName}_${timestamp}.xls`, html, 'application/vnd.ms-excel;charset=utf-8')
  message.value = '已导出开标后回测 Excel。'
}

async function calibrateFromActualBids() {
  if (!selectedRule.value) return
  error.value = ''
  try {
    const { data } = await api.post('/bid-strategy/calibrate', { rule: selectedRule.value, actualBids: actualBids.value })
    form.marketMean = String(data.marketMean || '')
    form.sigma = String(data.sigma || '')
    form.bidderMode = data.bidderMode || 'fixed'
    form.bidderCount = Number(data.bidderCount || form.bidderCount)
    form.bidderMin = form.bidderCount
    form.bidderMax = form.bidderCount
    message.value = `已用开标数据校准：μ=${money(form.marketMean || 0)}，σ=${money(form.sigma || 0)}，n=${form.bidderCount}。`
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

function runGameAfterSync(value: CostSyncContext) {
  if (!value.autoRunGame || !selectedRule.value) return
  const syncId = value.syncId || `${value.costLine}-${value.syncedAt}`
  if (lastAutoRunSyncId.value === syncId) return
  lastAutoRunSyncId.value = syncId
  window.setTimeout(() => {
    void runGame()
  }, 0)
}

function applyCostSync(payload: unknown) {
  if (!payload || typeof payload !== 'object') return
  const value = payload as CostSyncContext
  if (!value.costLine) return
  syncedCostContext.value = value
  if (value.runCode) selectedPricingRun.value = value.runCode
  form.floor = String(Math.round(Number(value.costLine)))
  const costLine = Number(value.costLine)
  form.step = String(Math.max(1000, Math.round((costLine * 0.005) / 1000) * 1000))
  form.ceiling = String(Math.round(Math.max(costLine * 1.2, costLine + Number(form.step) * 12)))
  form.sigma = String(Math.round(Number(form.ceiling) * 0.05))
  syncRecommendedRoundsIfAuto()
  syncedCostMessage.value = `${value.source || '单项反推'} 已同步成本线 C=${money(form.floor)}，项目数 ${value.itemCount || '-'}，时间 ${value.syncedAt || '-'}${value.autoRunGame ? '，已自动重新运行竞争推演' : ''}。`
  runGameAfterSync(value)
}

function readSyncedCost() {
  try {
    const payload = JSON.parse(localStorage.getItem('bid_generation_cost_context') || 'null')
    if (!payload?.costLine) {
      message.value = '暂无单项反推成本线。请先在单项报价反推页选择计价批次并同步成本，或直接选择计价批次后点击“应用批次成本”。'
      return
    }
    applyCostSync(payload)
  } catch {
    return
  }
}

function onStorage(event: StorageEvent) {
  if (event.key !== 'bid_generation_cost_context' || !event.newValue) return
  try {
    applyCostSync(JSON.parse(event.newValue))
  } catch {
    return
  }
}

onMounted(async () => {
  await Promise.all([loadRules(), loadRuleFiles(), loadPricingRuns()])
  readSyncedCost()
  window.addEventListener('storage', onStorage)
})

onBeforeUnmount(() => {
  window.removeEventListener('storage', onStorage)
  if (progressTimer) window.clearInterval(progressTimer)
  stopParseProgress()
})
</script>

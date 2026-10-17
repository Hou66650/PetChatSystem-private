import { FarmPanel } from '../components/FarmPanel';
import { preferences } from '@kit.ArkData';
import { util } from '@kit.ArkTS';
import { FarmAction, CareState, CareEvent, CareEventInput, CareSettingsInput, ChatMessage, ChatRequest, CompanionMemory, CompanionProfile, PetInfo } from '../model/Contracts';
import { PetApi } from '../service/PetApi';

@Entry
@Component
struct Index {
  @State private server: string = '';
  @State private rememberConnection: boolean = true;
  @State private allowLanHttp: boolean = false;
  @State private username: string = '';
  @State private password: string = '';
  @State private account: string = '';
  @State private pets: PetInfo[] = [];
  @State private selectedId: number = 0;
  @State private selectedName: string = '';
  @State private messages: ChatMessage[] = [];
  @State private draft: string = '';
  @State private busy: boolean = false;
  @State private status: string = '连接电脑，开始今天的陪伴';
  @State private error: string = '';
  @State private wide: boolean = true;
  @State private maxChars: number = 2000;
  @State private pendingText: string = '';
  @State private section: string = 'chat';
  @State private farmPending: boolean = false;
  @State private farmRequest: FarmAction | null = null;
  @State private farmOperation: string = '';
  @State private profile: CompanionProfile | null = null;
  @State private memoryId: number = 0;
  @State private memoryCategory: number = 0;
  @State private memoryValue: string = '';
  @State private careState: CareState | null = null;
  @State private careEnabled: boolean = true;
  @State private careEmotion: boolean = true;
  @State private quietStart: string = '22';
  @State private quietEnd: string = '8';
  @State private eventId: string = '';
  @State private eventTitle: string = '';
  @State private eventTime: string = '';
  @State private remindTime: string = '';
  @State private careNotice: string = '';
  @State private historySearch: string = '';
  private categoryKeys: string[] = ['pet_name', 'style', 'name', 'likes', 'dislikes', 'routine', 'goal', 'memory'];
  private categoryLabels: string[] = ['宠物昵称', '陪伴方式', '希望怎样称呼你', '喜欢的事', '不喜欢的事', '日常习惯', '近期计划', '共同记忆'];
  private pendingId: string = '';
  private api: PetApi = new PetApi();
  private scroller: Scroller = new Scroller();

  aboutToAppear(): void { this.loadConnection(); }

  private async loadConnection(): Promise<void> {
    this.busy = true;
    try {
      const context = this.getUIContext().getHostContext();
      if (!context) { return; }
      const store = await preferences.getPreferences(context, { name: 'connection' });
      this.rememberConnection = await store.get('remember', true) as boolean;
      if (this.rememberConnection) {
        this.server = await store.get('server', '') as string;
        this.username = await store.get('username', '') as string;
        this.allowLanHttp = await store.get('allowLanHttp', false) as boolean;
      }
    } catch (_) { /* The login form remains usable if local preferences cannot be read. */ }
    finally { this.busy = false; }
  }

  private async saveConnection(): Promise<void> {
    try {
      const context = this.getUIContext().getHostContext();
      if (!context) { return; }
      const store = await preferences.getPreferences(context, { name: 'connection' });
      await store.put('remember', this.rememberConnection);
      await store.put('server', this.rememberConnection ? this.server.trim() : '');
      await store.put('username', this.rememberConnection ? this.username : '');
      await store.put('allowLanHttp', this.rememberConnection && this.allowLanHttp);
      await store.flush();
    } catch (_) { /* Preference failures must never invalidate a successful login. */ }
  }

  private async connect(): Promise<void> {
    if (this.busy) { return; }
    this.busy = true; this.error = ''; this.status = '正在连接…';
    try {
      this.api.configure(this.server, this.allowLanHttp);
      const bootstrap = await this.api.bootstrap();
      const account = await this.api.login(this.username, this.password);
      this.password = '';
      await this.saveConnection();
      this.account = account.username;
      this.pets = bootstrap.pets;
      this.maxChars = bootstrap.maxMessageChars;
      this.selectedId = this.pets[0].id;
      this.selectedName = this.pets[0].name;
      this.messages = (await this.api.history(this.selectedId)).messages;
      this.status = '已连接 · 服务端 ' + bootstrap.appVersion;
    } catch (failure) {
      this.error = (failure as Error).message || '连接失败，请检查地址、Wi-Fi 和电脑服务';
      this.status = '连接未完成';
    } finally { this.busy = false; }
  }

  private async selectPet(pet: PetInfo): Promise<void> {
    if (this.busy || pet.id === this.selectedId || this.pendingId) { return; }
    this.busy = true; this.error = '';
    // Clear first so a failed request never displays a different pet's messages.
    this.selectedId = pet.id; this.selectedName = pet.name; this.messages = []; this.draft = ''; this.profile = null; this.resetEditors();
    try {
      this.messages = (await this.api.history(pet.id)).messages;
      if (this.section === 'profile') { this.profile = await this.api.companion(pet.id); }
      if (this.section === 'care') { this.applyCare(await this.api.care(pet.id)); }
    }
    catch (failure) { this.error = (failure as Error).message || '读取历史失败'; }
    finally { this.busy = false; }
  }

  private async refresh(): Promise<void> {
    if (this.busy) { return; }
    this.busy = true; this.error = '';
    try { this.messages = (await this.api.history(this.selectedId)).messages; }
    catch (failure) { this.error = (failure as Error).message || '读取历史失败'; }
    finally { this.busy = false; }
  }

  private async send(): Promise<void> {
    if (this.busy || (!this.pendingId && !this.draft.trim())) { return; }
    this.busy = true; this.error = '';
    if (!this.pendingId) {
      this.pendingId = util.generateRandomUUID(true);
      this.pendingText = this.draft.trim();
    }
    const request: ChatRequest = { petId: this.selectedId, message: this.pendingText, requestId: this.pendingId };
    try {
      const reply = await this.api.chat(request);
      const now = Date.now();
      const additions: ChatMessage[] = [
        { id: -now, petId: this.selectedId, role: 'user', content: this.pendingText, created_at: '' },
        { id: -now - 1, petId: this.selectedId, role: 'assistant', content: reply.reply, created_at: '' }
      ];
      this.messages = this.messages.concat(additions);
      this.pendingId = ''; this.pendingText = ''; this.draft = '';
      this.scroller.scrollEdge(Edge.Bottom);
    } catch (failure) {
      this.error = ((failure as Error).message || '发送失败') + '。重试会沿用原请求编号。';
    } finally { this.busy = false; }
  }

  private async disconnect(): Promise<void> {
    if (this.busy) { return; }
    this.busy = true;
    try { await this.api.logout(); }
    catch (_) { /* Always forget the local credential even when the server is unavailable. */ }
    finally {
      this.account = ''; this.password = ''; this.pets = []; this.messages = [];
      this.profile = null; this.section = 'chat'; this.resetEditors();
      this.selectedId = 0; this.selectedName = ''; this.pendingId = ''; this.pendingText = '';
      this.draft = ''; this.error = ''; this.status = '已退出'; this.busy = false;
    }
  }

  private async showProfile(): Promise<void> {
    if (this.busy) { return; }
    this.section = 'profile'; this.busy = true; this.error = ''; this.profile = null;
    try { this.profile = await this.api.companion(this.selectedId); }
    catch (failure) { this.error = (failure as Error).message || '读取陪伴档案失败'; }
    finally { this.busy = false; }
  }

  private async changeMemory(): Promise<void> {
    if (this.busy || !this.profile) { return; }
    this.busy = true; this.error = '';
    try { this.profile = await this.api.setMemory(this.selectedId, !this.profile.enabled); }
    catch (failure) { this.error = (failure as Error).message || '更新失败，请刷新确认'; }
    finally { this.busy = false; }
  }

  private resetEditors(): void {
    this.memoryId = 0; this.memoryValue = ''; this.memoryCategory = 0;
    this.careState = null; this.careNotice = ''; this.historySearch = ''; this.resetEvent();
  }

  private editMemory(memory: CompanionMemory): void {
    this.memoryId = memory.id; this.memoryValue = memory.value;
    this.memoryCategory = Math.max(0, this.categoryKeys.indexOf(memory.category));
  }

  private async saveMemoryEditor(): Promise<void> {
    if (this.busy || !this.memoryValue.trim()) { return; }
    this.busy = true; this.error = '';
    try {
      await this.api.saveMemory(this.selectedId, this.memoryId, this.categoryKeys[this.memoryCategory], this.memoryValue.trim());
      this.memoryId = 0; this.memoryValue = '';
      this.profile = await this.api.companion(this.selectedId);
    } catch (failure) { this.error = (failure as Error).message || '保存失败，请刷新确认'; }
    finally { this.busy = false; }
  }

  private confirmRemove(memory: CompanionMemory): void {
    this.getUIContext().showAlertDialog({
      title: '删除这条记忆？',
      message: (memory.petId === 0 ? '这条记忆由账号下所有宠物共用。' : '这条记忆属于当前宠物。') + '删除后无法撤销，聊天历史会保留。',
      primaryButton: { value: '保留', action: () => {} },
      secondaryButton: { value: '删除', action: () => { this.removeMemory(memory.id); } }
    });
  }

  private async removeMemory(id: number): Promise<void> {
    if (this.busy) { return; }
    this.busy = true; this.error = '';
    try {
      await this.api.removeMemory(this.selectedId, id);
      if (this.memoryId === id) { this.memoryId = 0; this.memoryValue = ''; }
      this.profile = await this.api.companion(this.selectedId);
    } catch (failure) { this.error = (failure as Error).message || '删除失败，请刷新确认'; }
    finally { this.busy = false; }
  }

  private applyCare(data: CareState): void {
    this.careState = data; this.careEnabled = data.settings.enabled === 1;
    this.careEmotion = data.settings.emotion === 1;
    this.quietStart = data.settings.quiet_start.toString(); this.quietEnd = data.settings.quiet_end.toString();
  }

  private async showCare(): Promise<void> {
    if (this.busy) { return; }
    this.section = 'care'; this.busy = true; this.error = ''; this.careState = null;
    try { this.applyCare(await this.api.care(this.selectedId)); }
    catch (failure) { this.error = (failure as Error).message || '读取关怀计划失败'; }
    finally { this.busy = false; }
  }

  private async saveCareSettings(): Promise<void> {
    if (this.busy) { return; }
    if (!/^([0-9]|1[0-9]|2[0-3])$/.test(this.quietStart) || !/^([0-9]|1[0-9]|2[0-3])$/.test(this.quietEnd)) {
      this.error = '免打扰起止小时请输入 0–23 的整数'; return;
    }
    this.busy = true; this.error = '';
    const data: CareSettingsInput = { enabled: this.careEnabled, emotion: this.careEmotion,
      quiet_start: Number(this.quietStart), quiet_end: Number(this.quietEnd) };
    try { this.applyCare(await this.api.saveCare(this.selectedId, data)); }
    catch (failure) { this.error = (failure as Error).message || '设置保存失败'; }
    finally { this.busy = false; }
  }

  private resetEvent(): void { this.eventId = ''; this.eventTitle = ''; this.eventTime = ''; this.remindTime = ''; }

  private beijingTime(seconds: number): string {
    return new Date((seconds + 8 * 3600) * 1000).toISOString().slice(0, 16).replace('T', ' ');
  }

  private parseBeijing(value: string): number {
    if (!/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(value)) { throw new Error('时间格式请填写 YYYY-MM-DD HH:mm（北京时间）'); }
    const result = Date.parse(value.replace(' ', 'T') + ':00+08:00') / 1000;
    if (!Number.isFinite(result) || this.beijingTime(result) !== value) { throw new Error('请填写真实有效的日期时间'); }
    return result;
  }

  private editEvent(event: CareEvent): void {
    this.eventId = event.id; this.eventTitle = event.title;
    this.eventTime = this.beijingTime(event.event_at); this.remindTime = this.beijingTime(event.remind_at);
  }

  private async saveEventEditor(): Promise<void> {
    if (this.busy || !this.eventTitle.trim()) { return; }
    this.busy = true; this.error = '';
    try {
      const data: CareEventInput = { title: this.eventTitle.trim(), event_at: this.parseBeijing(this.eventTime),
        remind_at: this.parseBeijing(this.remindTime) };
      this.applyCare(await this.api.saveEvent(this.selectedId, this.eventId, data)); this.resetEvent();
    } catch (failure) { this.error = (failure as Error).message || '保存计划失败'; }
    finally { this.busy = false; }
  }

  private async cancelEvent(id: string): Promise<void> {
    if (this.busy) { return; }
    this.busy = true; this.error = '';
    try { this.applyCare(await this.api.cancelEvent(this.selectedId, id)); if (this.eventId === id) { this.resetEvent(); } }
    catch (failure) { this.error = (failure as Error).message || '取消失败，请刷新确认'; }
    finally { this.busy = false; }
  }

  private async checkCare(): Promise<void> {
    if (this.busy) { return; }
    this.busy = true; this.error = '';
    try {
      const result = await this.api.claimCare(this.selectedId);
      this.careNotice = result.notice ? result.notice.message : '目前没有可领取的到期关怀。免打扰期间不提醒，每个账号每天最多一次。';
      this.applyCare(await this.api.care(this.selectedId));
    } catch (failure) { this.error = (failure as Error).message || '读取提醒失败'; }
    finally { this.busy = false; }
  }

  private eventStatus(state: string): string {
    if (state === 'draft') { return '待确认'; }
    if (state === 'scheduled') { return '已安排'; }
    if (state === 'cancelled') { return '已取消'; }
    if (state === 'delivered') { return '已提醒'; }
    if (state === 'superseded') { return '已被新计划替代'; }
    return '已结束';
  }

  @Builder
  private carePanel() {
    Scroll() {
      Column({ space: 16 }) {
        Row() {
          Text('主动关怀').fontSize(26).fontWeight(FontWeight.Bold).layoutWeight(1)
          Button('刷新').enabled(!this.busy).onClick(() => { this.showCare(); })
        }.width('100%')
        Text('北京时间 · 前台查看提醒；暂不支持应用关闭后的系统通知。').fontSize(14).fontColor('#775E51')
        if (this.careState) {
          if (!this.careState.memoryEnabled) { Text('长期记忆已暂停。请在陪伴档案中恢复记忆后管理计划。').fontColor('#9C2525') }
          Row({ space: 12 }) {
            Toggle({ type: ToggleType.Switch, isOn: this.careEnabled }).enabled(!this.busy)
              .onChange((value: boolean) => { this.careEnabled = value; })
            Text('时间关怀')
            Toggle({ type: ToggleType.Switch, isOn: this.careEmotion }).enabled(!this.busy)
              .onChange((value: boolean) => { this.careEmotion = value; })
            Text('情绪关怀')
          }
          Text('免打扰时段（0–23 点；起止相同表示全天不设免打扰）').fontSize(14)
          Row({ space: 12 }) {
            TextInput({ placeholder: '开始小时', text: this.quietStart }).layoutWeight(1).maxLength(2).enabled(!this.busy)
              .onChange((value: string) => { this.quietStart = value; })
            Text('至')
            TextInput({ placeholder: '结束小时', text: this.quietEnd }).layoutWeight(1).maxLength(2).enabled(!this.busy)
              .onChange((value: string) => { this.quietEnd = value; })
            Button('保存设置').enabled(!this.busy).onClick(() => { this.saveCareSettings(); })
          }.width('100%')
          Button('查看到期关怀').enabled(!this.busy && this.careState.memoryEnabled).onClick(() => { this.checkCare(); })
          if (this.careNotice) { Text(this.careNotice).padding(16).backgroundColor('#F8E3CF').borderRadius(12) }
          Text(this.eventId ? '修改／确认计划' : '添加计划').fontSize(20).fontWeight(FontWeight.Bold)
          TextInput({ placeholder: '例如：面试、考试、出差', text: this.eventTitle }).maxLength(60).enabled(!this.busy)
            .onChange((value: string) => { this.eventTitle = value; })
          TextInput({ placeholder: '事件时间：YYYY-MM-DD HH:mm', text: this.eventTime }).maxLength(16).enabled(!this.busy)
            .onChange((value: string) => { this.eventTime = value; })
          TextInput({ placeholder: '提醒时间：YYYY-MM-DD HH:mm', text: this.remindTime }).maxLength(16).enabled(!this.busy)
            .onChange((value: string) => { this.remindTime = value; })
          Row({ space: 12 }) {
            Button('保存并确认').enabled(!this.busy && this.careState.memoryEnabled && this.eventTitle.trim().length > 0)
              .onClick(() => { this.saveEventEditor(); })
            Button('清空表单').enabled(!this.busy).onClick(() => { this.resetEvent(); })
          }
          Text('我的计划').fontSize(20).fontWeight(FontWeight.Bold)
          if (this.careState.events.length === 0) { Text('暂无计划。聊天里提到的近期安排也会在这里等待确认。').fontColor('#775E51') }
          ForEach(this.careState.events, (event: CareEvent) => {
            Column({ space: 10 }) {
              Text(event.title + ' · ' + this.eventStatus(event.state)).fontSize(19).fontWeight(FontWeight.Bold)
              Text('事件：' + this.beijingTime(event.event_at)).fontSize(15)
              Text('提醒：' + this.beijingTime(event.remind_at)).fontSize(15)
              if (event.state === 'draft' || event.state === 'scheduled') {
                Row({ space: 12 }) {
                  Button(event.state === 'draft' ? '查看并确认' : '修改时间').enabled(!this.busy).onClick(() => { this.editEvent(event); })
                  Button('取消计划').enabled(!this.busy).onClick(() => { this.cancelEvent(event.id); })
                }
              }
            }.width('100%').alignItems(HorizontalAlign.Start).padding(16).backgroundColor('#FFFFFF').borderRadius(16)
          }, (event: CareEvent) => event.id)
        } else { Text(this.busy ? '正在读取…' : '读取失败，请刷新。') }
      }.width('100%').padding(20).alignItems(HorizontalAlign.Start)
    }.layoutWeight(1).width('100%')
  }

  @Builder
  private companionPanel() {
    Scroll() {
      Column({ space: 18 }) {
        Row() {
          Text('陪伴档案').fontSize(26).fontWeight(FontWeight.Bold).layoutWeight(1)
          Button('刷新').enabled(!this.busy).onClick(() => { this.showProfile(); })
        }.width('100%')
        if (this.profile) {
          Text(this.profile.name + ' · ' + this.profile.species).fontSize(24).fontWeight(FontWeight.Bold)
          Text(this.profile.role).fontSize(16).fontColor('#775E51')
          Text('已经交流 ' + this.profile.interactionCount.toString() + ' 次').fontSize(16)
          Text('陪伴方式：' + this.profile.companionStyle).fontSize(18)
          Row({ space: 16 }) {
            Text(this.profile.enabled ? '长期记忆已开启' : '长期记忆已暂停').layoutWeight(1)
            Button(this.profile.enabled ? '暂停记忆' : '恢复记忆')
              .enabled(!this.busy).onClick(() => { this.changeMemory(); })
          }.width('100%')
          Text('此设置影响账号下所有宠物。暂停后保留已有档案，不再使用长期记忆；聊天历史仍保留。')
            .fontSize(14).fontColor('#775E51')
          Text(this.memoryId ? '编辑记忆' : '添加记忆／设置昵称').fontSize(20).fontWeight(FontWeight.Bold)
          Select(this.categoryLabels.map((label: string): SelectOption => ({ value: label })))
            .selected(this.memoryCategory).value(this.categoryLabels[this.memoryCategory]).enabled(!this.busy && this.memoryId === 0)
            .onSelect((index: number) => { this.memoryCategory = index; })
          TextInput({ placeholder: '填写 1–80 字', text: this.memoryValue }).maxLength(80).enabled(!this.busy)
            .onChange((value: string) => { this.memoryValue = value; })
          Text('昵称和共同记忆属于当前宠物；其余偏好由账号下所有宠物共用。').fontSize(14).fontColor('#775E51')
          Row({ space: 12 }) {
            Button('保存记忆').enabled(!this.busy && this.memoryValue.trim().length > 0).onClick(() => { this.saveMemoryEditor(); })
            Button('取消编辑').enabled(!this.busy).onClick(() => { this.memoryId = 0; this.memoryValue = ''; })
          }
          Text('它记得的事').fontSize(20).fontWeight(FontWeight.Bold)
          if (this.profile.memories.length === 0) {
            Text('还没有记录。可以在聊天中告诉它你的称呼或陪伴偏好。').fontColor('#775E51')
          }
          ForEach(this.profile.memories, (memory: CompanionMemory) => {
            Column({ space: 8 }) {
              Text(memory.label).fontSize(14).fontColor('#775E51')
              Text(memory.value).fontSize(18).copyOption(CopyOptions.InApp)
              Row({ space: 12 }) {
                Button('编辑').enabled(!this.busy).onClick(() => { this.editMemory(memory); })
                Button('删除').enabled(!this.busy).onClick(() => { this.confirmRemove(memory); })
              }
            }.width('100%').alignItems(HorizontalAlign.Start).padding(16)
              .backgroundColor('#FFFFFF').borderRadius(16)
          }, (memory: CompanionMemory) => memory.id.toString())
        } else {
          Text(this.busy ? '正在读取档案…' : '暂未取得档案，请点击刷新。').padding(24)
        }
      }.width('100%').alignItems(HorizontalAlign.Start).padding(20)
    }.layoutWeight(1).width('100%')
  }

  @Builder
  private workspacePanel() {
    Column({ space: 8 }) {
      Flex({ wrap: FlexWrap.Wrap }) {
        Button('聊天').margin(4).backgroundColor(this.section === 'chat' ? '#98512D' : '#775E51')
          .enabled(!this.busy && !this.farmPending).onClick(() => { this.section = 'chat'; })
        Button('陪伴档案').margin(4).backgroundColor(this.section === 'profile' ? '#98512D' : '#775E51')
          .enabled(!this.busy && !this.farmPending && this.pendingText.length === 0).onClick(() => { this.showProfile(); })
        Button('主动关怀').margin(4).backgroundColor(this.section === 'care' ? '#98512D' : '#775E51')
          .enabled(!this.busy && !this.farmPending && this.pendingText.length === 0).onClick(() => { this.showCare(); })
        Button('种植园').margin(4).backgroundColor(this.section === 'farm' ? '#98512D' : '#775E51')
          .enabled(!this.busy && !this.farmPending && this.pendingText.length === 0).onClick(() => { this.section = 'farm'; })
      }.padding({ top: 12, left: 20 }).width('100%')
      if (this.section === 'chat') { this.chatPanel(); }
      else if (this.section === 'care') { this.carePanel(); }
      else if (this.section === 'farm') { FarmPanel({ api: this.api, busy: $busy, error: $error, pending: $farmPending, request: $farmRequest, operation: $farmOperation }); }
      else { this.companionPanel(); }
    }.layoutWeight(1).height('100%')
  }

  @Builder
  private loginPanel() {
    Scroll() {
      Column({ space: 18 }) {
        Text('让陪伴，离你近一点').fontSize(30).fontWeight(FontWeight.Bold).fontColor('#51392E')
        Text('使用派特岛账号登录').fontSize(16).fontColor('#775E51')
        TextInput({ placeholder: '电脑服务地址，例如 http://192.168.1.10:5003', text: this.server })
          .onChange((value: string) => { this.server = value; }).enabled(!this.busy)
        Row({ space: 12 }) {
          Toggle({ type: ToggleType.Switch, isOn: this.allowLanHttp })
            .onChange((value: boolean) => { this.allowLanHttp = value; }).enabled(!this.busy)
          Text('允许本地开发 HTTP（可信局域网 / USB 调试）').fontSize(14).layoutWeight(1)
        }.width('100%')
        TextInput({ placeholder: '用户名', text: this.username })
          .onChange((value: string) => { this.username = value; }).maxLength(128).enabled(!this.busy)
        TextInput({ placeholder: '密码', text: this.password }).type(InputType.Password)
          .onChange((value: string) => { this.password = value; }).maxLength(1024).enabled(!this.busy)
        Row({ space: 12 }) {
          Toggle({ type: ToggleType.Switch, isOn: this.rememberConnection }).enabled(!this.busy)
            .onChange((value: boolean) => { this.rememberConnection = value; this.saveConnection(); })
          Text('记住地址和用户名（不保存密码）').fontSize(14).layoutWeight(1)
        }.width('100%')
        Button(this.busy ? '连接中…' : '进入派特岛').width('100%').height(48).backgroundColor('#98512D')
          .enabled(!this.busy && this.username.length > 0 && this.password.length > 0 && this.server.length > 0)
          .onClick(() => { this.connect(); })
        Text('平板与电脑连接同一 Wi-Fi。账号需先在电脑服务中注册。').fontSize(14).fontColor('#775E51')
        Text('开发预览 · 原生聊天已接入；3D 小岛与语音正在迁移').fontSize(13).fontColor('#775E51')
      }.width('100%').constraintSize({ maxWidth: 560 }).padding(24)
    }.layoutWeight(1).width('100%')
  }

  @Builder
  private petPicker() {
    Column({ space: 12 }) {
      Text('我的伙伴').fontSize(20).fontWeight(FontWeight.Bold).fontColor('#51392E')
      ForEach(this.pets, (pet: PetInfo) => {
        Button(pet.name).width('100%').height(52)
          .backgroundColor(pet.id === this.selectedId ? '#98512D' : '#F2E4D8')
          .fontColor(pet.id === this.selectedId ? '#FFFFFF' : '#51392E')
          .enabled(!this.busy && !this.farmPending && this.pendingText.length === 0)
          .onClick(() => { this.selectPet(pet); })
      }, (pet: PetInfo) => pet.id.toString())
    }.padding(16).width(this.wide ? 210 : '100%')
  }

  @Builder
  private chatPanel() {
    Column({ space: 12 }) {
      Row() {
        Text(this.selectedName + ' · 陪你聊聊').fontSize(24).fontWeight(FontWeight.Bold).layoutWeight(1)
        Button('刷新历史').enabled(!this.busy && this.pendingText.length === 0).onClick(() => { this.refresh(); })
      }.width('100%')
      TextInput({ placeholder: '搜索最近聊天记录', text: this.historySearch })
        .onChange((value: string) => { this.historySearch = value; })
      List({ space: 12, scroller: this.scroller }) {
        ForEach(this.messages.filter((item: ChatMessage): boolean => item.content.toLowerCase().includes(this.historySearch.toLowerCase())), (message: ChatMessage) => {
          ListItem() {
            Column({ space: 6 }) {
              Text(message.role === 'user' ? '我' : this.selectedName).fontSize(13).fontColor('#775E51')
              Text(message.content).fontSize(18).fontColor('#51392E').copyOption(CopyOptions.InApp)
            }.alignItems(HorizontalAlign.Start).padding(16).width('100%').borderRadius(16)
              .backgroundColor(message.role === 'user' ? '#F8E3CF' : '#FFFFFF')
          }
        }, (message: ChatMessage) => message.id.toString())
        if (this.messages.length > 0 && this.historySearch &&
          this.messages.filter((item: ChatMessage): boolean => item.content.toLowerCase().includes(this.historySearch.toLowerCase())).length === 0) {
          ListItem() { Text('最近记录中没有匹配内容。').padding(24).fontColor('#775E51') }
        }
        if (this.messages.length === 0) {
          ListItem() { Text('说声你好，开始今天的故事。').padding(24).fontColor('#775E51') }
        }
      }.layoutWeight(1).width('100%')
      if (this.pendingText.length > 0) {
        Text('待确认：' + this.pendingText).fontSize(14).maxLines(2).fontColor('#775E51')
      }
      Row({ space: 12 }) {
        TextArea({ placeholder: '想和它说些什么？', text: this.draft }).layoutWeight(1).height(88)
          .maxLength(this.maxChars).enabled(!this.busy && this.pendingText.length === 0)
          .onChange((value: string) => { this.draft = value; })
        Button(this.busy ? '请稍候…' : (this.pendingText ? '重试' : '发送')).height(48).backgroundColor('#98512D')
          .enabled(!this.busy && (this.draft.trim().length > 0 || this.pendingText.length > 0))
          .onClick(() => { this.send(); })
      }.width('100%')
    }.padding(20).layoutWeight(1).width('100%')
  }

  build() {
    Column() {
      Row({ space: 12 }) {
        Text('派特岛').fontSize(28).fontWeight(FontWeight.Bold).fontColor('#51392E')
        Text(this.status).fontSize(13).fontColor('#775E51').layoutWeight(1)
        if (this.account) {
          Text(this.account).fontSize(14)
          Button('退出').enabled(!this.busy && !this.farmPending).onClick(() => { this.disconnect(); })
        }
      }.padding(20).width('100%')
      if (this.error) { Text(this.error).fontColor('#9C2525').fontSize(15).padding(12).width('100%') }
      if (!this.account) {
        this.loginPanel()
      } else {
        if (this.wide) {
          Row() { this.petPicker(); this.workspacePanel() }.layoutWeight(1).width('100%')
        } else {
          Column() {
            Select(this.pets.map((pet: PetInfo): SelectOption => ({ value: pet.name })))
              .value(this.selectedName).enabled(!this.busy && !this.farmPending && this.pendingText.length === 0)
              .onSelect((index: number) => { this.selectPet(this.pets[index]); })
            this.workspacePanel()
          }.layoutWeight(1).width('100%')
        }
      }
    }.width('100%').height('100%').backgroundColor('#FFF8F0')
      .onAreaChange((_old: Area, current: Area) => { this.wide = Number(current.width) >= 840; })
  }
}

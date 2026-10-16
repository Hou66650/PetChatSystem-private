import { util } from '@kit.ArkTS';
import { ChatMessage, ChatRequest, CompanionMemory, CompanionProfile, PetInfo } from '../model/Contracts';
import { PetApi } from '../service/PetApi';

@Entry
@Component
struct Index {
  @State private server: string = '';
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
  @State private profile: CompanionProfile | null = null;
  private pendingId: string = '';
  private api: PetApi = new PetApi();
  private scroller: Scroller = new Scroller();

  private async connect(): Promise<void> {
    if (this.busy) { return; }
    this.busy = true; this.error = ''; this.status = '正在连接…';
    try {
      this.api.configure(this.server, this.allowLanHttp);
      const bootstrap = await this.api.bootstrap();
      const account = await this.api.login(this.username, this.password);
      this.password = '';
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
    this.selectedId = pet.id; this.selectedName = pet.name; this.messages = []; this.draft = ''; this.profile = null;
    try {
      this.messages = (await this.api.history(pet.id)).messages;
      if (this.section === 'profile') { this.profile = await this.api.companion(pet.id); }
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
      this.profile = null; this.section = 'chat';
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
          Text('它记得的事').fontSize(20).fontWeight(FontWeight.Bold)
          if (this.profile.memories.length === 0) {
            Text('还没有记录。可以在聊天中告诉它你的称呼或陪伴偏好。').fontColor('#775E51')
          }
          ForEach(this.profile.memories, (memory: CompanionMemory) => {
            Column({ space: 8 }) {
              Text(memory.label).fontSize(14).fontColor('#775E51')
              Text(memory.value).fontSize(18).copyOption(CopyOptions.InApp)
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
      Row({ space: 12 }) {
        Button('聊天').backgroundColor(this.section === 'chat' ? '#98512D' : '#775E51')
          .enabled(!this.busy).onClick(() => { this.section = 'chat'; })
        Button('陪伴档案').backgroundColor(this.section === 'profile' ? '#98512D' : '#775E51')
          .enabled(!this.busy && this.pendingText.length === 0).onClick(() => { this.showProfile(); })
      }.padding({ top: 12, left: 20 }).width('100%')
      if (this.section === 'chat') { this.chatPanel(); }
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
          Text('允许本地开发 HTTP（仅可信局域网）').fontSize(14).layoutWeight(1)
        }.width('100%')
        TextInput({ placeholder: '用户名', text: this.username })
          .onChange((value: string) => { this.username = value; }).maxLength(128).enabled(!this.busy)
        TextInput({ placeholder: '密码', text: this.password }).type(InputType.Password)
          .onChange((value: string) => { this.password = value; }).maxLength(1024).enabled(!this.busy)
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
          .enabled(!this.busy && this.pendingText.length === 0)
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
      List({ space: 12, scroller: this.scroller }) {
        ForEach(this.messages, (message: ChatMessage) => {
          ListItem() {
            Column({ space: 6 }) {
              Text(message.role === 'user' ? '我' : this.selectedName).fontSize(13).fontColor('#775E51')
              Text(message.content).fontSize(18).fontColor('#51392E').copyOption(CopyOptions.InApp)
            }.alignItems(HorizontalAlign.Start).padding(16).width('100%').borderRadius(16)
              .backgroundColor(message.role === 'user' ? '#F8E3CF' : '#FFFFFF')
          }
        }, (message: ChatMessage) => message.id.toString())
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
          Button('退出').enabled(!this.busy).onClick(() => { this.disconnect(); })
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
              .value(this.selectedName).enabled(!this.busy && this.pendingText.length === 0)
              .onSelect((index: number) => { this.selectPet(this.pets[index]); })
            this.workspacePanel()
          }.layoutWeight(1).width('100%')
        }
      }
    }.width('100%').height('100%').backgroundColor('#FFF8F0')
      .onAreaChange((_old: Area, current: Area) => { this.wide = Number(current.width) >= 840; })
  }
}

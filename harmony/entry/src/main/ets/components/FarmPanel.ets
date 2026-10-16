import { util } from '@kit.ArkTS';
import { FarmAction, FarmBed, FarmPlant, FarmShopItem, FarmSpecies, FarmState, FarmStock } from '../model/Contracts';
import { HttpStatusError, PetApi } from '../service/PetApi';

@Component
export struct FarmPanel {
  api: PetApi = new PetApi();
  @Link busy: boolean;
  @Link error: string;
  @Link pending: boolean;
  @State private garden: FarmState | null = null;
  @State private species: string = 'cosmos';
  @Link operation: string;
  @Link request: FarmAction | null;
  @State private notice: string = '';

  aboutToAppear(): void { this.refresh(); }

  private stock(id: string): number {
    if (!this.garden) { return 0; }
    const found = this.garden.inventory.find((item: FarmStock): boolean => item.id === id);
    return found ? found.quantity : 0;
  }

  private speciesName(id: string): string {
    if (!this.garden) { return id; }
    const found = this.garden.catalog.find((item: FarmSpecies): boolean => item.id === id);
    return found ? found.name : id;
  }

  private canPlant(bed: FarmBed): boolean {
    if (!this.garden || !this.garden.started || this.stock('seed:' + this.species) < 1) { return false; }
    const found = this.garden.catalog.find((item: FarmSpecies): boolean => item.id === this.species);
    return !!found && found.plantable && bed.nursery === (found.kind === 'tree');
  }

  private ready(): boolean { return !this.busy && !this.pending; }

  private async refresh(): Promise<void> {
    if (this.busy) { return; }
    this.busy = true; this.error = '';
    try {
      this.garden = await this.api.farm();
      if (this.request && this.garden.recentRequests.includes(this.request.token)) {
        this.request = null; this.pending = false; this.notice = '已确认上次操作完成，库存已同步。';
      }
    } catch (failure) { this.error = (failure as Error).message || '读取种植园失败'; }
    finally { this.busy = false; }
  }

  private async run(operation: string, data: FarmAction): Promise<void> {
    if (this.busy || this.pending) { return; }
    this.operation = operation; this.request = data; this.pending = true;
    await this.retry();
  }

  private async retry(): Promise<void> {
    if (this.busy || !this.request) { return; }
    this.busy = true; this.error = ''; this.notice = '';
    try {
      this.garden = await this.api.farmAction(this.operation, this.request);
      this.request = null; this.pending = false; this.notice = '操作成功，花园与库存已同步。';
    } catch (failure) {
      this.error = (failure as Error).message || '园艺操作失败';
      if (failure instanceof HttpStatusError && failure.status >= 400 && failure.status < 500) {
        // Rejected transactions are rolled back by the server. Network failures retain the token.
        this.request = null; this.pending = false;
      } else {
        this.error += '。结果待确认，请刷新或使用原编号重试，避免重复消耗库存。';
      }
    } finally { this.busy = false; }
  }

  private simple(operation: string): void {
    this.run(operation, { token: util.generateRandomUUID(true) });
  }

  private plant(bed: FarmBed): void {
    this.run('plant', { token: util.generateRandomUUID(true), bed: bed.id, species: this.species });
  }

  private care(operation: string, bed: FarmBed, plant: FarmPlant): void {
    this.run(operation, { token: util.generateRandomUUID(true), bed: bed.id, plant: plant.id });
  }

  private buy(item: FarmShopItem): void {
    this.getUIContext().showAlertDialog({
      title: '购买' + item.name + '？',
      message: '消耗 ' + item.price.toString() + ' 枚游戏代币，购买 1 份。不涉及现金支付。',
      primaryButton: { value: '取消', action: () => {} },
      secondaryButton: { value: '购买', action: () => {
        this.run('buy', { token: util.generateRandomUUID(true), item: item.id, quantity: 1 });
      } }
    });
  }

  @Builder
  private bedCard(bed: FarmBed) {
    Column({ space: 10 }) {
      Text(bed.name + (bed.nursery ? ' · 树苗专用' : ' · 花卉与作物')).fontSize(19).fontWeight(FontWeight.Bold)
      if (bed.plant) {
        Text(this.speciesName(bed.plant.species) + ' · ' + (bed.plant.ready ? '已成熟' : '生长阶段 ' + bed.plant.stage.toString() + '/10')).fontSize(17)
        Progress({ value: Math.round(bed.plant.progress * 100), total: 100, type: ProgressType.Linear }).width('100%')
        if (!bed.plant.ready) {
          Text('预计剩余约 ' + Math.max(1, Math.ceil(bed.plant.remaining / 60)).toString() + ' 分钟（刷新更新）').fontSize(14)
        }
        Flex({ wrap: FlexWrap.Wrap }) {
          Button(bed.plant.watered ? '今日已浇水' : '浇水').margin(4)
            .enabled(this.ready() && !bed.plant.watered && !bed.plant.ready)
            .onClick(() => { if (bed.plant) { this.care('water', bed, bed.plant); } })
          Button(bed.plant.fertilized ? '今日已施肥' : '施肥 · 消耗 1 份').margin(4)
            .enabled(this.ready() && !bed.plant.fertilized && !bed.plant.ready && this.stock('fertilizer') > 0)
            .onClick(() => { if (bed.plant) { this.care('fertilize', bed, bed.plant); } })
          Button('收获').margin(4).enabled(this.ready() && bed.plant.ready)
            .onClick(() => { if (bed.plant) { this.care('harvest', bed, bed.plant); } })
        }
      } else {
        Text('空闲 · 准备种下 ' + this.speciesName(this.species)).fontSize(16)
        Button('播种 · 消耗 1 份种子').enabled(this.ready() && this.canPlant(bed))
          .onClick(() => { this.plant(bed); })
      }
    }.width('100%').alignItems(HorizontalAlign.Start).padding(16).backgroundColor('#FFFFFF').borderRadius(16)
  }

  build() {
    Scroll() {
      Column({ space: 16 }) {
        Row() {
          Text('种植园').fontSize(26).fontWeight(FontWeight.Bold).layoutWeight(1)
          Button('刷新').enabled(!this.busy).onClick(() => { this.refresh(); })
        }.width('100%')
        Text('生长由服务器计时，离线不会枯萎。这里管理种植床；岛上 3D 移栽与摆放尚未迁移。')
          .fontSize(14).fontColor('#775E51')
        if (this.notice) { Text(this.notice).fontColor('#436B3F') }
        if (this.pending) {
          Text('上次操作待确认，请保持在此页面，刷新或重试。').fontColor('#9C2525')
          Button('原编号重试').enabled(!this.busy).onClick(() => { this.retry(); })
        }
        if (this.garden) {
          Row({ space: 12 }) {
            Text('代币：' + this.garden.balance.toString()).fontSize(20).layoutWeight(1)
            Button(this.garden.dailyClaimed ? '今日已领取' : '领取每日代币')
              .enabled(this.ready() && !this.garden.dailyClaimed).onClick(() => { this.simple('daily'); })
          }.width('100%')
          if (!this.garden.started) {
            Text('领取入门礼后开始种植，包含种子、花盆和肥料。')
            Button('领取园艺入门礼').enabled(this.ready()).onClick(() => { this.simple('start'); })
          } else {
            Text('选择播种种类').fontSize(20).fontWeight(FontWeight.Bold)
            Select(this.garden.catalog.filter((item: FarmSpecies): boolean => item.plantable)
              .map((item: FarmSpecies): SelectOption => ({ value: item.name })))
              .value(this.speciesName(this.species)).enabled(this.ready())
              .onSelect((index: number) => {
                if (this.garden) { this.species = this.garden.catalog.filter((item: FarmSpecies): boolean => item.plantable)[index].id; }
              })
            Text('可用种子：' + this.stock('seed:' + this.species).toString()).fontSize(15)
            ForEach(this.garden.beds, (bed: FarmBed) => { this.bedCard(bed); }, (bed: FarmBed) => bed.id)
            Text('我的库存').fontSize(20).fontWeight(FontWeight.Bold)
            ForEach(this.garden.inventory, (item: FarmStock) => {
              if (item.quantity > 0) { Text(item.name + ' × ' + item.quantity.toString()).fontSize(16) }
            }, (item: FarmStock) => item.id)
            Button('制作宠物零食 · 消耗 1 个小南瓜').enabled(this.ready() && this.stock('pumpkin') > 0)
              .onClick(() => { this.simple('cook'); })
            Text('零食进入账号宠物用品库存，喂食入口尚未迁移。').fontSize(13).fontColor('#775E51')
            Text('园艺商店').fontSize(20).fontWeight(FontWeight.Bold)
            ForEach(this.garden.shop, (item: FarmShopItem) => {
              Row({ space: 12 }) {
                Text(item.name).layoutWeight(1).fontSize(16)
                Button(item.price.toString() + ' 代币 / 份')
                  .enabled(this.ready() && !!this.garden && this.garden.balance >= item.price)
                  .onClick(() => { this.buy(item); })
              }.width('100%').padding(12).backgroundColor('#FFFFFF').borderRadius(12)
            }, (item: FarmShopItem) => item.id)
          }
        } else { Text(this.busy ? '正在读取花园…' : '读取失败，请刷新。') }
      }.width('100%').alignItems(HorizontalAlign.Start).padding(20)
    }.width('100%').layoutWeight(1)
  }
}

import { http } from '@kit.NetworkKit';
import { Account, CompanionProfile, MemorySettings, ApiError, Bootstrap, ChatReply, ChatRequest, History, LoginRequest } from '../model/Contracts';

// Memory-only session: never write passwords, cookies or conversations to logs/preferences.
export class PetApi {
  private origin: string = '';
  private cookie: string = '';
  private cookieName: string = 'session';
  private generation: number = 0;

  configure(raw: string, allowLanHttp: boolean): void {
    const origin = raw.trim().replace(/\/$/, '');
    const match = /^(https?):\/\/([a-zA-Z0-9.-]+)(?::([0-9]{1,5}))?$/.exec(origin);
    if (!match || (match[3] && (Number(match[3]) < 1 || Number(match[3]) > 65535))) {
      throw new Error('请输入服务器根地址，例如 http://192.168.1.10:5003');
    }
    const octets = match[2].split('.').map((part: string): number => Number(part));
    const isIpv4 = /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/.test(match[2]) &&
      octets.every((part: number): boolean => part >= 0 && part <= 255);
    const privateIp = isIpv4 && (octets[0] === 10 ||
      (octets[0] === 192 && octets[1] === 168) ||
      (octets[0] === 172 && octets[1] >= 16 && octets[1] <= 31));
    if (match[1] === 'http' && (!allowLanHttp || !privateIp)) {
      throw new Error('HTTP 仅限显式开启的局域网开发；公网请使用 HTTPS');
    }
    this.clear();
    this.origin = origin;
  }

  clear(): void { this.cookie = ''; this.generation += 1; }

  private async request(path: string, method: http.RequestMethod, body: string = ''): Promise<string> {
    const task = http.createHttp();
    const generation = this.generation;
    try {
      const response = await task.request(this.origin + '/api/mobile/v1' + path, {
        method: method,
        header: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'Cookie': this.cookie },
        extraData: body,
        expectDataType: http.HttpDataType.STRING,
        usingCache: false,
        connectTimeout: 10000,
        readTimeout: 90000,
        maxLimit: 2 * 1024 * 1024
      });
      if (generation !== this.generation) { throw new Error('连接已切换，请重试'); }
      const result = response.result as string;
      if (response.responseCode === 401) { this.clear(); }
      if (response.responseCode < 200 || response.responseCode >= 300) {
        let reason = '请求失败（' + response.responseCode.toString() + '）';
        try {
          const failure = JSON.parse(result) as ApiError;
          if (failure.error) { reason = failure.error; }
        } catch (_) { /* Non-JSON proxy errors keep the status-only message. */ }
        throw new Error(reason);
      }
      // Prefer the actual response header; NetworkKit cookies may use a cookie-list format.
      const headers = response.header as Record<string, string | string[]>;
      let found = false;
      if (headers) {
        for (const key of Object.keys(headers)) {
          if (key.toLowerCase() !== 'set-cookie') { continue; }
          const value = headers[key];
          const values: string[] = typeof value === 'string' ? [value] : value;
          for (const item of values) {
            if (this.readSessionCookie(item)) { found = true; }
          }
        }
      }
      if (!found && response.cookies) { this.readSessionCookie(response.cookies); }
      return result;
    } finally {
      task.destroy();
    }
  }

  private readSessionCookie(raw: string): boolean {
    const escapedName = this.cookieName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const match = new RegExp('(?:^|[;,\\s])' + escapedName + '=([^;\\s,]*)').exec(raw);
    if (match) {
      this.cookie = match[1] ? this.cookieName + '=' + match[1] : '';
      return true;
    }
    // libcurl cookie-list: domain, includeSubdomains, path, secure, expiry, name, value.
    for (const line of raw.split(/\r?\n/)) {
      const fields = line.split('\t');
      if (fields.length === 7 && fields[5] === this.cookieName &&
        !/[;\s,]/.test(fields[6])) {
        this.cookie = fields[6] ? this.cookieName + '=' + fields[6] : '';
        return true;
      }
    }
    return false;
  }

  async bootstrap(): Promise<Bootstrap> {
    const data = JSON.parse(await this.request('/bootstrap', http.RequestMethod.GET)) as Bootstrap;
    if (data.apiVersion !== 1 || !Array.isArray(data.pets) || data.pets.length === 0) {
      throw new Error('服务器版本不兼容或没有宠物');
    }
    this.cookieName = data.sessionCookieName;
    return data;
  }

  async login(username: string, password: string): Promise<Account> {
    const body: LoginRequest = { username: username, password: password };
    this.clear();
    const account = JSON.parse(await this.request('/session', http.RequestMethod.POST, JSON.stringify(body))) as Account;
    if (!this.cookie) { throw new Error('服务器没有返回登录凭证，请检查连接'); }
    return account;
  }

  async logout(): Promise<void> {
    try { await this.request('/logout', http.RequestMethod.POST, '{}'); }
    finally { this.clear(); }
  }

  async history(petId: number): Promise<History> {
    return JSON.parse(await this.request('/history?petId=' + petId.toString(), http.RequestMethod.GET)) as History;
  }

  async companion(petId: number): Promise<CompanionProfile> {
    return JSON.parse(await this.request('/companion?petId=' + petId.toString(), http.RequestMethod.GET)) as CompanionProfile;
  }

  async setMemory(petId: number, enabled: boolean): Promise<CompanionProfile> {
    const data: MemorySettings = { enabled: enabled };
    return JSON.parse(await this.request('/companion?petId=' + petId.toString(), http.RequestMethod.POST,
      JSON.stringify(data))) as CompanionProfile;
  }

  async chat(data: ChatRequest): Promise<ChatReply> {
    return JSON.parse(await this.request('/chat', http.RequestMethod.POST, JSON.stringify(data))) as ChatReply;
  }
}

/**
 * 果蝇复眼采样 —— 浏览器 / Node 通用。
 *
 * 用的是 FlyGym 的**真实采样几何**（ommatidia_id_map，512×450，含鱼眼畸变
 * zoom=2.72 / distortion=3.8），不是我编的近似：场景先渲染成相机画面，
 * 再按这张表把每个像素归到 721 个小眼之一（每个约 239 像素）。
 *
 * 职责边界：本模块只做「相机画面 → 721 个亮度」。
 * 画面怎么来（canvas 画上传的图 / 游戏场景截屏）由调用方决定，
 * 这样 Node 里不需要 canvas 也能做 parity 验证。
 *
 * 朝向：实测 相机x ↔ 六边形y、相机y ↔ 六边形x（相关 1.000，精确转置）。
 * 画六边形图时必须交换两轴，否则用户会看到自己的图被转了 90°。
 */
const Retina = (() => {
  class R {
    /**
     * @param {Uint16Array} idmap 长度 w*h，0=背景，1..721=小眼编号
     * @param {object} meta retina.json 的内容
     */
    constructor(idmap, meta) {
      this.meta = meta;                    // 累积器要用里面的小眼中心坐标
      this.w = meta.width; this.h = meta.height;
      this.idmap = idmap;
      this.npx = Float64Array.from(meta.pixels_per_ommatidium);
      this.perm = Int32Array.from(meta.flygym_to_flyvis);
      this.n = meta.n_ommatidia;
      if (idmap.length !== this.w * this.h)
        throw new Error(`idmap 长度 ${idmap.length} != ${this.w}×${this.h}`);
      // pale=1 读蓝通道，yellow=0 读绿通道（FlyGym 原样；果蝇真实通道是紫外/蓝/绿，
      // 紫外无法从 sRGB 照片恢复，所以这里只有两个通道）
      this.pale = Int8Array.from(meta.pale_type_mask || new Array(this.n).fill(0));
      this._sum = new Float64Array(this.n + 1);
      this._sumB = new Float64Array(this.n + 1);
      this._gym = new Float64Array(this.n);
      this.out = new Float64Array(this.n);
    }

    /**
     * 相机画面 → 721 个小眼亮度（已换成 flyvis 柱顺序）。
     * @param {ArrayLike<number>} frame 长度 w*h 的灰度值（任意量纲，建议 0..1）
     * @returns {Float64Array} 长度 721，顺序 = flyvis_net.json 的 lattice
     */
    sample(frame) {
      const { idmap, _sum, _gym, npx, perm, out, n } = this;
      _sum.fill(0);
      for (let i = 0; i < idmap.length; i++) {
        const id = idmap[i];
        if (id !== 0) _sum[id] += frame[i];
      }
      for (let k = 0; k < n; k++) _gym[k] = _sum[k + 1] / npx[k];
      for (let j = 0; j < n; j++) out[j] = _gym[perm[j]];   // flygym 序 → flyvis 柱序
      return out;
    }

    /**
     * 双通道采样，和 FlyGym 的 _raw_image_to_hex_pxls 一致：
     * 每个小眼只读**它自己那一路** —— pale 读蓝、yellow 读绿，像拜耳滤镜。
     * 结果仍是每柱一个标量，因为 flyvis 每个小眼只吃一个数（它是用光流训练的，
     * 没有颜色通道）。颜色信息到这里就被压成一维了，这是模型的限制，不是果蝇的。
     * @returns {Float64Array} 721 个值（flyvis 柱序）
     */
    sampleGB(frameG, frameB) {
      const { idmap, _sum, _sumB, _gym, npx, perm, out, n, pale } = this;
      _sum.fill(0); _sumB.fill(0);
      for (let i = 0; i < idmap.length; i++) {
        const id = idmap[i];
        if (id === 0) continue;
        _sum[id] += frameG[i]; _sumB[id] += frameB[i];
      }
      for (let k = 0; k < n; k++)
        _gym[k] = (pale[k] ? _sumB[k + 1] : _sum[k + 1]) / npx[k];
      for (let j = 0; j < n; j++) out[j] = _gym[perm[j]];
      return out;
    }

    /** 每个 flyvis 柱是不是 pale 型（画彩色马赛克要用） */
    paleByColumn() {
      const a = new Int8Array(this.n);
      for (let j = 0; j < this.n; j++) a[j] = this.pale[this.perm[j]];
      return a;
    }
  }

  return {
    Retina: R,
    /** Node：从 retina_map.bin + retina.json 构造 */
    fromBuffer(buf, meta) {
      const u16 = new Uint16Array(buf.buffer, buf.byteOffset, buf.byteLength / 2);
      return new R(u16, typeof meta === "string" ? JSON.parse(meta) : meta);
    },
    /** 浏览器：从已解码的 retina_map.png 像素（RGBA）构造 */
    fromImageData(data, meta) {
      const n = data.length / 4;
      const u16 = new Uint16Array(n);
      for (let i = 0; i < n; i++) u16[i] = (data[i * 4] << 8) | data[i * 4 + 1];
      return new R(u16, typeof meta === "string" ? JSON.parse(meta) : meta);
    },
  };
})();

if (typeof module !== "undefined" && module.exports) module.exports = Retina;

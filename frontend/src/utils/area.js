/** 预览图选框 -> 视频原始帧坐标 的换算（纯函数，便于单测） */

export function clamp(v, lo, hi) {
  return Math.min(Math.max(v, lo), hi)
}

/**
 * @param {{left:number, top:number, width:number, height:number}} box 预览图上的选框（CSS 像素）
 * @param {{width:number, height:number}} displaySize 预览图在页面上的渲染尺寸
 * @param {{width:number, height:number}} frameSize 视频原始帧尺寸
 * @returns {{xmin:number, ymin:number, xmax:number, ymax:number}|null} 帧坐标；尺寸非法时返回 null
 */
export function toFrameRect(box, displaySize, frameSize) {
  const dw = displaySize?.width
  const dh = displaySize?.height
  const fw = frameSize?.width
  const fh = frameSize?.height
  // 预览图没加载出来（尺寸为 0）时绝不能换算，否则缩放系数是 Infinity
  if (!dw || !dh || !fw || !fh) return null
  const scaleX = fw / dw
  const scaleY = fh / dh
  return {
    xmin: clamp(Math.round(box.left * scaleX), 0, fw),
    ymin: clamp(Math.round(box.top * scaleY), 0, fh),
    xmax: clamp(Math.round((box.left + box.width) * scaleX), 0, fw),
    ymax: clamp(Math.round((box.top + box.height) * scaleY), 0, fh)
  }
}

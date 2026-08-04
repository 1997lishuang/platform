export interface RegionOption {
  code: string
  name: string
  scope: string
}

export const regionOptions: RegionOption[] = [
  { code: 'CN', name: '全国', scope: '全国' },
  { code: 'CN-SOUTH', name: '华南', scope: '广东、广西、福建、海南' },
  { code: 'CN-EAST', name: '华东', scope: '江苏、浙江、上海、安徽、山东、江西' },
  { code: 'CN-NORTH', name: '华北', scope: '北京、天津、河北、山西、内蒙古中部' },
  { code: 'CN-CENTRAL', name: '华中', scope: '湖北、湖南、河南' },
  { code: 'CN-SOUTHWEST', name: '西南', scope: '四川、重庆、贵州、云南' },
  { code: 'CN-NORTHWEST', name: '西北', scope: '陕西、甘肃、青海、宁夏、新疆' },
  { code: 'CN-NORTHEAST', name: '东北', scope: '辽宁、吉林、黑龙江' }
]

export function regionLabel(code: string | null | undefined) {
  const matched = regionOptions.find((item) => item.code === code)
  return matched ? `${matched.name}（${matched.code}）` : code || '-'
}

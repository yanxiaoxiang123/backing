import type { ThemeConfig } from 'antd'
import { ui } from './uiTheme'

/** Shared by the research and strategy routes; DL remains the visual reference. */
export const researchTheme: ThemeConfig = {
  token: {
    colorPrimary: '#222222',
    colorInfo: '#1677ff',
    colorLink: '#242424',
    colorText: '#242424',
    colorTextSecondary: ui.muted,
    colorBorder: '#dedede',
    colorBorderSecondary: '#e8e8e8',
    colorBgContainer: ui.panel,
    colorBgElevated: ui.panel,
    colorBgLayout: ui.main,
    borderRadius: 7,
    borderRadiusLG: 14,
    controlHeight: 40,
    fontSize: 15,
  },
  components: {
    Button: { borderRadius: 7, controlHeight: 40 },
    Input: { borderRadius: 7, controlHeight: 40 },
    InputNumber: { borderRadius: 7, controlHeight: 40 },
    Select: { borderRadius: 7, controlHeight: 40 },
    DatePicker: { borderRadius: 7, controlHeight: 40, fontSize: 14 },
    Card: { borderRadiusLG: 14, headerBg: ui.main, headerHeight: 54 },
    Table: {
      headerBg: ui.main,
      headerColor: '#707070',
      borderColor: '#e8e8e8',
      rowHoverBg: ui.main,
      fontSize: 14,
    },
  },
}

/** 股票领域 API。实现暂时由兼容 facade 提供，便于渐进迁移调用方。 */
export {
  getStocks,
  getAllStocks,
  getStock,
  getStockKline,
  getStockIndicators,
  getStockOverview,
  syncStocks,
  syncKline,
  submitSyncStocks,
  submitSyncKline,
} from './api'

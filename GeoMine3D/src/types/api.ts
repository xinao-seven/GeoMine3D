export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

export interface PageQuery {
  page?: number
  pageSize?: number
  keyword?: string
}

import { useState, useEffect, useCallback } from 'react'

/** Generic hook for fetching data from the API with loading/error states. */
export function useApi(fetcher, deps = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const refetch = useCallback(() => {
    setLoading(true)
    setError(null)
    fetcher()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { refetch() }, [refetch])

  return { data, loading, error, refetch }
}

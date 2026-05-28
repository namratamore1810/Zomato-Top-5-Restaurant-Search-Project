import { useState, useEffect, useRef } from 'react'
import { 
  Sparkles, 
  Star, 
  MapPin, 
  Heart, 
  Plus, 
  Minus, 
  Search, 
  RefreshCw,
  Utensils
} from 'lucide-react'

// Constants
const API_BASE = 'http://localhost:8000/api'

// Interfaces matching backend Pydantic models
interface UserPreferences {
  location: string
  budget: 'low' | 'medium' | 'high'
  cuisine: string
  min_rating: number
  additional_preferences: string | null
  top_n: number
}

interface RecommendationItem {
  rank: number
  restaurant_id: string
  name: string
  cuisine: string
  rating: number
  estimated_cost: string
  explanation: string
  budget_tier?: string
}

interface RecommendationMeta {
  candidates_considered: number
  top_n: number
  degraded: boolean
  degraded_reason: string | null
}

interface RecommendationResult {
  status: 'success'
  summary: string | null
  preferences: UserPreferences
  recommendations: RecommendationItem[]
  meta: RecommendationMeta
}

interface NoResultsResponse {
  status: 'no_results'
  message: string
  suggestions: string[]
}

interface ErrorResponse {
  status: 'error'
  message: string
  code: string
}

type ApiResponse = RecommendationResult | NoResultsResponse | ErrorResponse

function App() {
  // Input Form States
  const [location, setLocation] = useState<string>('')
  const [budget, setBudget] = useState<'low' | 'medium' | 'high'>('medium')
  const [cuisineInput, setCuisineInput] = useState<string>('')
  const [minRating, setMinRating] = useState<number>(4.0)
  const [numResults, setNumResults] = useState<number>(5)
  const [additionalPrefs, setAdditionalPrefs] = useState<string>('')

  // Metadata Lookup States
  const [locations, setLocations] = useState<string[]>([])
  const [cuisines, setCuisines] = useState<string[]>([])
  const [filteredCuisines, setFilteredCuisines] = useState<string[]>([])
  const [showCuisineDropdown, setShowCuisineDropdown] = useState<boolean>(false)
  const [activeIndex, setActiveIndex] = useState<number>(-1)

  // API State
  const [loading, setLoading] = useState<boolean>(false)
  const [apiResponse, setApiResponse] = useState<ApiResponse | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [initialLoading, setInitialLoading] = useState<boolean>(true)

  // Favorites state
  const [favorites, setFavorites] = useState<string[]>([])

  // Refs for closing autocomplete dropdown
  const autocompleteRef = useRef<HTMLDivElement>(null)

  // Fetch locations and cuisines on mount
  useEffect(() => {
    const fetchMetadata = async () => {
      try {
        const [locRes, cuisRes] = await Promise.all([
          fetch(`${API_BASE}/locations`),
          fetch(`${API_BASE}/cuisines`)
        ])
        
        if (locRes.ok && cuisRes.ok) {
          const locData = await locRes.json()
          const cuisData = await cuisRes.json()
          
          setLocations(locData)
          setCuisines(cuisData)
          
          if (locData.length > 0) {
            setLocation(locData[0])
          }
        }
      } catch (err) {
        console.error('Error fetching backend metadata:', err)
        setErrorMessage('Could not connect to the API server. Make sure the backend is running on port 8000.')
      } finally {
        setInitialLoading(false)
      }
    }
    fetchMetadata()
  }, [])

  // Auto-close autocomplete on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (autocompleteRef.current && !autocompleteRef.current.contains(event.target as Node)) {
        setShowCuisineDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Handle cuisine input change
  const handleCuisineChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setCuisineInput(val)
    
    if (val.trim() === '') {
      setFilteredCuisines([])
      setShowCuisineDropdown(false)
      return
    }

    const filtered = cuisines.filter(c => 
      c.toLowerCase().includes(val.toLowerCase())
    ).slice(0, 8)
    
    setFilteredCuisines(filtered)
    setShowCuisineDropdown(filtered.length > 0)
    setActiveIndex(-1)
  }

  // Keyboard navigation for autocomplete
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showCuisineDropdown) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex(prev => (prev < filteredCuisines.length - 1 ? prev + 1 : 0))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex(prev => (prev > 0 ? prev - 1 : filteredCuisines.length - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (activeIndex >= 0 && activeIndex < filteredCuisines.length) {
        selectCuisine(filteredCuisines[activeIndex])
      } else if (filteredCuisines.length > 0) {
        selectCuisine(filteredCuisines[0])
      }
    } else if (e.key === 'Escape') {
      setShowCuisineDropdown(false)
    }
  }

  const selectCuisine = (val: string) => {
    setCuisineInput(val)
    setShowCuisineDropdown(false)
  }

  // Submit search preferences
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!location) {
      setErrorMessage('Please select a location.')
      return
    }
    if (!cuisineInput.trim()) {
      setErrorMessage('Please enter or select a cuisine.')
      return
    }

    setLoading(true)
    setApiResponse(null)
    setErrorMessage(null)

    const payload: UserPreferences = {
      location: location,
      budget: budget,
      cuisine: cuisineInput,
      min_rating: minRating,
      additional_preferences: additionalPrefs.trim() || null,
      top_n: numResults
    }

    try {
      const response = await fetch(`${API_BASE}/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (!response.ok) {
        throw new Error('API server returned an error response.')
      }

      const data: ApiResponse = await response.json()
      setApiResponse(data)
      
      if (data.status === 'error') {
        setErrorMessage(data.message)
      }
    } catch (err) {
      console.error('Error fetching recommendations:', err)
      setErrorMessage('Something went wrong while connecting to the recommendation service.')
    } finally {
      setLoading(false)
    }
  }

  // Helper for title casing location
  const titleCase = (str: string) => {
    if (!str) return ''
    return str.split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
  }

  // Toggle favorite status
  const toggleFavorite = (id: string) => {
    setFavorites(prev => 
      prev.includes(id) ? prev.filter(fId => fId !== id) : [...prev, id]
    )
  }

  // Map budget tier labels
  const getBudgetDisplay = (tier: string) => {
    if (tier.toLowerCase() === 'low') return 'Budget'
    if (tier.toLowerCase() === 'medium') return 'Medium'
    return 'Premium'
  }

  // Format percentage
  const getMatchPercentage = (rank: number) => {
    return 100 - (rank - 1) * 6
  }

  return (
    <div className="app-container">
      {/* Header section matching image2 */}
      <header className="header-section">
        <div className="discover-pill">
          <Sparkles size={12} className="text-primary" />
          Discover the Future of Dining
        </div>
        <h1 className="main-title">TasteTrail<span>AI</span></h1>
        <p className="subtitle">
          Personalized restaurant discovery powered by AI and real-world dining preferences.
        </p>
      </header>

      {/* Small notification bar matching image2 */}
      <div className="search-spacer">
        {initialLoading ? 'Connecting to TasteTrail service...' : 'Start search to generate AI recommendations'}
      </div>

      {/* Form Container Card matching image2 */}
      <form className="form-card" onSubmit={handleSubmit}>
        {/* AREA Field */}
        <div className="form-group">
          <label className="form-label" htmlFor="area-select">Area</label>
          <div className="select-wrapper">
            <select
              id="area-select"
              className="custom-select"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              disabled={locations.length === 0}
            >
              {locations.length > 0 ? (
                locations.map(loc => (
                  <option key={loc} value={loc}>
                    {titleCase(loc)}
                  </option>
                ))
              ) : (
                <option value="">Loading locations...</option>
              )}
            </select>
          </div>
        </div>

        {/* MINIMUM RATING Field */}
        <div className="form-group">
          <div className="form-label form-label-with-val">
            <span>Minimum Rating</span>
            <span className="form-label-val">{minRating.toFixed(1)} ★</span>
          </div>
          <div className="slider-container">
            <input
              type="range"
              min="0.0"
              max="5.0"
              step="0.1"
              className="rating-slider"
              value={minRating}
              onChange={(e) => setMinRating(parseFloat(e.target.value))}
              style={{
                background: `linear-gradient(to right, var(--accent-red) 0%, var(--accent-red) ${(minRating / 5) * 100}%, #252630 ${(minRating / 5) * 100}%, #252630 100%)`
              }}
            />
            <span 
              className="slider-tooltip"
              style={{ left: `calc(${(minRating / 5) * 100}% + ${(2.5 - minRating) * 5}px)` }}
            >
              {minRating.toFixed(2)}
            </span>
          </div>
        </div>

        {/* BUDGET RANGE Field */}
        <div className="form-group">
          <label className="form-label">Budget Range</label>
          <div className="budget-buttons">
            <button
              type="button"
              className={`budget-btn ${budget === 'low' ? 'selected' : ''}`}
              onClick={() => setBudget('low')}
            >
              <div className="budget-circle" />
              Budget
            </button>
            <button
              type="button"
              className={`budget-btn ${budget === 'medium' ? 'selected' : ''}`}
              onClick={() => setBudget('medium')}
            >
              <div className="budget-circle" />
              Medium
            </button>
            <button
              type="button"
              className={`budget-btn ${budget === 'high' ? 'selected' : ''}`}
              onClick={() => setBudget('high')}
            >
              <div className="budget-circle" />
              Premium
            </button>
          </div>
        </div>

        {/* NUMBER OF RESULTS Field */}
        <div className="form-group">
          <label className="form-label" htmlFor="results-count">Number of Results</label>
          <div className="counter-wrapper">
            <div className="counter-display" id="results-count">
              {numResults}
            </div>
            <div className="counter-controls">
              <button
                type="button"
                className="counter-btn"
                onClick={() => setNumResults(prev => Math.max(1, prev - 1))}
              >
                <Minus size={14} />
              </button>
              <button
                type="button"
                className="counter-btn"
                onClick={() => setNumResults(prev => Math.min(20, prev + 1))}
              >
                <Plus size={14} />
              </button>
            </div>
          </div>
        </div>

        {/* PREFERRED CUISINES Field */}
        <div className="form-group autocomplete-container" ref={autocompleteRef}>
          <label className="form-label" htmlFor="cuisine-input">Preferred Cuisines</label>
          <div style={{ position: 'relative' }}>
            <input
              id="cuisine-input"
              type="text"
              placeholder="Search or select cuisines... (e.g. Italian, North Indian)"
              className="custom-input"
              value={cuisineInput}
              onChange={handleCuisineChange}
              onKeyDown={handleKeyDown}
              onFocus={() => cuisineInput && setFilteredCuisines(cuisines.filter(c => c.toLowerCase().includes(cuisineInput.toLowerCase())).slice(0, 8))}
            />
            <Search size={16} style={{ position: 'absolute', right: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          </div>
          {showCuisineDropdown && filteredCuisines.length > 0 && (
            <ul className="suggestions-list">
              {filteredCuisines.map((cuis, idx) => (
                <li
                  key={cuis}
                  className={`suggestion-item ${idx === activeIndex ? 'active' : ''}`}
                  onClick={() => selectCuisine(cuis)}
                >
                  {cuis}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* ADDITIONAL PREFERENCES Field */}
        <div className="form-group">
          <label className="form-label" htmlFor="additional-input">Additional Preferences</label>
          <textarea
            id="additional-input"
            placeholder="Describe your perfect dining experience..."
            className="custom-textarea"
            value={additionalPrefs}
            onChange={(e) => setAdditionalPrefs(e.target.value)}
          />
        </div>

        {/* SUBMIT BUTTON */}
        <button type="submit" className="submit-btn" disabled={loading}>
          {loading ? (
            <>
              <RefreshCw className="animate-spin" size={18} style={{ animation: 'spinSlow 1s linear infinite' }} />
              Finding your top picks…
            </>
          ) : (
            <>
              <Sparkles size={18} />
              Get AI Recommendations
            </>
          )}
        </button>
      </form>

      {/* Loading Spinner */}
      {loading && (
        <div className="loading-container">
          <div className="spinner-ring" />
          <div className="loading-label">Finding your top picks…</div>
        </div>
      )}

      {/* Error alert banner */}
      {errorMessage && (
        <div className="alert-banner error">
          <div className="alert-title">Error</div>
          <div>{errorMessage}</div>
        </div>
      )}

      {/* API Response display */}
      {apiResponse && (
        <main>
          {/* Success Recommendations List */}
          {apiResponse.status === 'success' && (
            <>
              {apiResponse.meta.degraded && (
                <div className="alert-banner warning">
                  <div className="alert-title">Degraded recommendation mode</div>
                  <div>
                    {apiResponse.meta.degraded_reason === 'llm_api_error' 
                      ? 'The AI ranking engine is temporarily unavailable. Displaying search results sorted by rating.' 
                      : 'The AI recommendations are partially complete. Backfilled using standard ranking.'}
                  </div>
                </div>
              )}

              {/* Display overview summary if present */}
              {apiResponse.summary && (
                <div style={{ maxWidth: '900px', margin: '3rem auto 1rem', padding: '1.5rem', backgroundColor: '#121319', border: '1px solid #1f212a', borderRadius: '12px' }}>
                  <div style={{ fontWeight: '700', fontSize: '1rem', color: 'var(--text-primary)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <Sparkles size={16} style={{ color: 'var(--accent-cyan)' }} />
                    AI Overview Summary
                  </div>
                  <p style={{ lineHeight: '1.6', fontSize: '0.95rem' }}>{apiResponse.summary}</p>
                </div>
              )}

              <div className="results-header-section">
                <h2 className="results-title">Your top picks</h2>
              </div>

              {/* Grid matching design/image1.png */}
              <div className="cards-grid">
                {apiResponse.recommendations.map((item, idx) => {
                  const cuisineList = item.cuisine.split(',').map(c => c.trim()).filter(Boolean)
                  const isFav = favorites.includes(item.restaurant_id)

                  return (
                    <div 
                      className="recommendation-card" 
                      key={item.restaurant_id}
                      style={{ animationDelay: `${idx * 0.1}s` }}
                    >
                      <div className="card-main-content">
                        {/* Rank and Match row */}
                        <div className="card-header-row">
                          <span className="card-rank">Rank #{item.rank}</span>
                          <span className="match-badge">
                            {getMatchPercentage(item.rank)}% Match
                          </span>
                        </div>

                        {/* Favorite button */}
                        <div className="heart-row">
                          <button 
                            type="button" 
                            className={`heart-btn ${isFav ? 'active' : ''}`}
                            onClick={() => toggleFavorite(item.restaurant_id)}
                          >
                            <Heart size={16} fill={isFav ? 'var(--accent-red)' : 'none'} />
                          </button>
                        </div>

                        {/* Restaurant Name */}
                        <h3 className="card-title">{item.name}</h3>

                        {/* Rating, budget, cost, location metadata */}
                        <div className="card-meta-row">
                          <span className="meta-rating">
                            <Star size={14} />
                            {item.rating.toFixed(1)}
                          </span>
                          <span className="meta-dot">·</span>
                          <span className="meta-budget">
                            <Utensils size={13} style={{ color: 'var(--text-muted)' }} />
                            {getBudgetDisplay(item.budget_tier || 'medium')}
                          </span>
                          <span className="meta-dot">·</span>
                          <span className="meta-cost">{item.estimated_cost}</span>
                          <span className="meta-location">
                            <MapPin size={13} />
                            {titleCase(location)}, Bangalore
                          </span>
                        </div>

                        {/* Cuisine Chips */}
                        <div className="cuisine-chips">
                          {cuisineList.map(cuis => (
                            <span className="cuisine-chip" key={cuis}>
                              {cuis.toLowerCase()}
                            </span>
                          ))}
                        </div>
                      </div>

                      {/* Sparkle container at bottom of card */}
                      <div className="why-container">
                        <div className="why-header">
                          <Sparkles size={13} />
                          Why AI Picked It
                        </div>
                        <div className="why-text">
                          "{item.explanation}"
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Grid Footer metadata */}
              <div className="metadata-footer">
                <span>
                  Considered {apiResponse.meta.candidates_considered} matching restaurants
                </span>
                <span>
                  Showing top {apiResponse.recommendations.length} recommendations
                </span>
              </div>
            </>
          )}

          {/* Empty Results state */}
          {apiResponse.status === 'no_results' && (
            <div className="alert-banner warning">
              <div className="alert-title">{apiResponse.message}</div>
              {apiResponse.suggestions && apiResponse.suggestions.length > 0 && (
                <>
                  <p><strong>Try:</strong></p>
                  <ul className="alert-suggestions">
                    {apiResponse.suggestions.map((tip, idx) => (
                      <li key={idx}>{tip}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}
        </main>
      )}
    </div>
  )
}

export default App

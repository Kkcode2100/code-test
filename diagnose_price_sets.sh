#!/bin/bash

# Price Set Diagnostic Tool
# Analyzes the price structure and suggests fixes

set -e

# Configuration
MORPHEUS_URL="${MORPHEUS_URL:-https://xdjmorpheapp01}"
MORPHEUS_TOKEN="${MORPHEUS_TOKEN:-9fcc4426-c89a-4430-b6d7-99d5950fc1cc}"
PRICE_PREFIX="${PRICE_PREFIX:-IOH-CP}"

echo "🔧 GCP Price Set Diagnostic Tool"
echo "=================================="

# Function to make API calls
api_call() {
    local method="$1"
    local endpoint="$2"
    local data="$3"
    
    if [ "$method" = "GET" ]; then
        curl -s -k -H "Authorization: BEARER $MORPHEUS_TOKEN" \
             -H "Content-Type: application/json" \
             "$MORPHEUS_URL/api/$endpoint"
    else
        curl -s -k -X "$method" \
             -H "Authorization: BEARER $MORPHEUS_TOKEN" \
             -H "Content-Type: application/json" \
             -d "$data" \
             "$MORPHEUS_URL/api/$endpoint"
    fi
}

echo "🔍 Step 1: Analyzing existing prices..."

# Get prices and analyze them
prices_json=$(api_call GET "prices?max=2000&phrase=$PRICE_PREFIX")
price_count=$(echo "$prices_json" | jq -r '.prices | length // 0')

echo "✅ Found $price_count prices with prefix $PRICE_PREFIX"

if [ "$price_count" -eq 0 ]; then
    echo "❌ No prices found. Please run create-prices first."
    exit 1
fi

echo ""
echo "📊 Price Type Analysis:"
echo "$prices_json" | jq -r '
.prices[] | 
select(.name | contains("'"$PRICE_PREFIX"'")) |
"\(.priceType): \(.name)"
' | sort | uniq -c | sort -nr

echo ""
echo "🏷️ Machine Family Analysis:"
echo "$prices_json" | jq -r '
.prices[] | 
select(.name | contains("'"$PRICE_PREFIX"'")) |
.name
' | grep -oE "(N2D?|E2|C2?D?|M[0-9]+U?|T2D|A2)" | sort | uniq -c | sort -nr

echo ""
echo "🔍 Step 2: Checking existing price sets..."

price_sets_json=$(api_call GET "price-sets?max=1000&phrase=$PRICE_PREFIX")
price_set_count=$(echo "$price_sets_json" | jq -r '.priceSets | length // 0')

echo "📦 Found $price_set_count existing price sets"

if [ "$price_set_count" -gt 0 ]; then
    echo ""
    echo "Existing price sets:"
    echo "$price_sets_json" | jq -r '.priceSets[] | "• \(.name) (\(.code)) - \(.prices | length) prices"'
fi

echo ""
echo "🔍 Step 3: Analyzing the error pattern..."

echo "The error indicates that Morpheus expects either:"
echo "1. A complete 'Everything' price set with ALL required price types"
echo "2. Separate price sets for individual price types"
echo ""
echo "Current issue: Trying to mix 'Memory Only' and 'Cores Only' in one price set"
echo "Solution: Create separate price sets for each price type"

echo ""
echo "💡 Recommended Fix Strategy:"
echo "Instead of grouping by machine family, group by price type within each family"
echo ""

# Analyze what price sets we should create
echo "🔧 Generating corrected price set structure..."

echo "$prices_json" | jq -r '
.prices[] | 
select(.name | contains("'"$PRICE_PREFIX"'")) |
{
    id: .id,
    name: .name,
    priceType: .priceType,
    family: (.name | 
        if test("\\b(N2D|N2|E2|C2D|C2|M[0-9]+U|T2D|A2)\\b"; "i") then
            capture("\\b(?<family>N2D|N2|E2|C2D|C2|M[0-9]+U|T2D|A2)\\b"; "i").family
        else
            "unknown"
        end
    )
}
' | jq -s '
group_by(.family) | 
map({
    family: .[0].family,
    priceTypes: group_by(.priceType) | 
    map({
        priceType: .[0].priceType,
        count: length,
        prices: map(.id)
    })
})
' > price_analysis.json

echo ""
echo "📋 Suggested Price Sets to Create:"
cat price_analysis.json | jq -r '
.[] | 
"Family: \(.family | ascii_upcase)" as $header |
(.priceTypes[] | 
"  • \(.priceType | ascii_upcase) price set: \(.count) prices"
) | 
if . == (.priceTypes[0] | "  • \(.priceType | ascii_upcase) price set: \(.count) prices") then
    [$header, .]
else
    [.]
end | 
.[]
'

echo ""
echo "🚀 Would you like me to create the corrected price sets? (y/N)"
read -r response

if [[ "$response" =~ ^[Yy]$ ]]; then
    echo ""
    echo "🔧 Creating corrected price sets..."
    
    # Create separate price sets for each family + price type combination
    created_count=0
    
    while IFS= read -r family_data; do
        family=$(echo "$family_data" | jq -r '.family')
        
        while IFS= read -r price_type_data; do
            price_type=$(echo "$price_type_data" | jq -r '.priceType')
            price_ids=$(echo "$price_type_data" | jq -c '.prices')
            count=$(echo "$price_type_data" | jq -r '.count')
            
            if [ "$count" -eq 0 ]; then
                continue
            fi
            
            # Create price set name and code
            price_set_name="$PRICE_PREFIX - GCP - ${family^^} - ${price_type^} (asia-southeast2)"
            price_set_code="${PRICE_PREFIX,,}.gcp-${family,,}-${price_type,,}-asia_southeast2"
            
            echo "Creating: $price_set_name"
            
            # Check if it already exists
            existing=$(api_call GET "price-sets?code=$price_set_code")
            if echo "$existing" | jq -e '.priceSets | length > 0' >/dev/null; then
                echo "  ⏭️  Already exists, skipping"
                continue
            fi
            
            # Create the price set payload
            price_list=$(echo "$price_ids" | jq '[.[] | {id: .}]')
            
            payload=$(jq -n \
                --arg name "$price_set_name" \
                --arg code "$price_set_code" \
                --argjson prices "$price_list" \
                '{
                    priceSet: {
                        name: $name,
                        code: $code,
                        type: "fixed",
                        priceUnit: "hour",
                        regionCode: "'"${PRICE_PREFIX,,}"'",
                        prices: $prices
                    }
                }')
            
            # Create the price set
            result=$(api_call POST "price-sets" "$payload")
            
            if echo "$result" | jq -e '.success // .priceSet' >/dev/null; then
                echo "  ✅ Created successfully"
                ((created_count++))
            else
                echo "  ❌ Failed:"
                echo "$result" | jq -r '.errors // .message // .'
            fi
            
        done < <(echo "$family_data" | jq -c '.priceTypes[]')
        
    done < <(cat price_analysis.json | jq -c '.[]')
    
    echo ""
    echo "📊 Summary: Created $created_count price sets successfully"
    
    # Clean up
    rm -f price_analysis.json
    
else
    echo "👋 Exiting without making changes"
    echo ""
    echo "💡 To manually fix the issue:"
    echo "1. Create separate price sets for each price type (cores, memory, storage)"
    echo "2. Don't mix different price types in the same price set"
    echo "3. Use 'fixed' type instead of 'component' for price sets"
fi
"""
Billing Rules Configuration for DaVinci AI Platform

All pricing, wallet, and billing logic is centralized here.
Modify these values to change business rules without touching application code.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class PricingTier:
    """Defines a single pricing tier based on call duration."""
    min_duration_seconds: int
    max_duration_seconds: int
    price_euros: float
    display_name: str


@dataclass
class BillingRules:
    """Master configuration for all billing rules."""
    
    # ============= PRICING TIERS =============
    pricing_tiers: List[PricingTier] = None
    
    # ============= WALLET CONFIGURATION =============
    minimum_balance_euros: float = 5.00
    low_balance_threshold_euros: float = 10.00
    critical_balance_threshold_euros: float = 2.00
    
    # ============= TOP-UP CONFIGURATION =============
    topup_presets_euros: List[float] = None
    min_topup_amount_euros: float = 5.00
    max_topup_amount_euros: float = 500.00
    
    # ============= BILLING CYCLE =============
    billing_period_days: int = 30
    invoice_generation_day: int = 1  # 1st of each month
    
    # ============= ENTERPRISE FEATURES =============
    enable_volume_discounts: bool = False
    volume_discount_threshold_calls: int = 100  # Per month
    volume_discount_percentage: float = 0.10  # 10% off
    
    # ============= GRACE PERIOD =============
    enable_grace_period: bool = True
    grace_period_hours: int = 24  # Allow calls even if balance is €0
    
    # ============= NOTIFICATIONS =============
    notify_low_balance: bool = True
    notify_call_completed: bool = False
    notify_topup_success: bool = True
    notify_payment_failed: bool = True
    
    # ============= DATA RETENTION =============
    call_logs_retention_days: int = 90
    transaction_history_retention_days: int = 365
    
    # ============= ANALYTICS =============
    enable_call_recordings: bool = True
    enable_sentiment_tracking: bool = True
    enable_transcript_storage: bool = True
    
    def __post_init__(self):
        """Initialize default values if not provided."""
        if self.pricing_tiers is None:
            # Default pricing structure (can be modified as needed)
            self.pricing_tiers = [
                PricingTier(0, 300, 2.00, "0-5 min"),       # 0-5 min = €2.00
                PricingTier(301, 600, 3.50, "5-10 min"),    # 5-10 min = €3.50
                PricingTier(601, 900, 5.00, "10-15 min"),   # 10-15 min = €5.00
                PricingTier(901, 99999, 7.00, "15+ min"),   # 15+ min = €7.00
            ]
        
        if self.topup_presets_euros is None:
            self.topup_presets_euros = [10.00, 20.00, 50.00, 100.00]
    
    def calculate_call_cost(self, duration_seconds: int) -> float:
        """
        Calculate cost for a call based on duration.
        
        Args:
            duration_seconds: Call duration in seconds
            
        Returns:
            Cost in euros
        """
        for tier in self.pricing_tiers:
            if tier.min_duration_seconds <= duration_seconds <= tier.max_duration_seconds:
                base_cost = tier.price_euros
                
                # Apply volume discount if enabled
                # (Volume discount logic would check monthly call count)
                return base_cost
        
        # Fallback: charge highest tier
        return self.pricing_tiers[-1].price_euros
    
    def apply_volume_discount(self, base_cost: float, monthly_calls: int) -> float:
        """
        Apply volume discount if tenant qualifies.
        
        Args:
            base_cost: Original call cost
            monthly_calls: Number of calls this month
            
        Returns:
            Discounted cost
        """
        if not self.enable_volume_discounts:
            return base_cost
        
        if monthly_calls >= self.volume_discount_threshold_calls:
            discount = base_cost * self.volume_discount_percentage
            return base_cost - discount
        
        return base_cost
    
    def get_estimated_calls_remaining(self, balance_euros: float) -> int:
        """
        Estimate how many average calls can be made with current balance.
        
        Args:
            balance_euros: Current wallet balance
            
        Returns:
            Estimated number of calls
        """
        if not self.pricing_tiers:
            return 0
        
        avg_cost = sum(t.price_euros for t in self.pricing_tiers) / len(self.pricing_tiers)
        
        if avg_cost > 0:
            return int(balance_euros / avg_cost)
        
        return 0
    
    def should_block_calls(self, balance_euros: float, last_topup_timestamp: int) -> bool:
        """
        Determine if calls should be blocked due to insufficient balance.
        
        Args:
            balance_euros: Current wallet balance
            last_topup_timestamp: Unix timestamp of last top-up
            
        Returns:
            True if calls should be blocked
        """
        import time
        
        # If balance is above minimum, allow calls
        if balance_euros >= self.minimum_balance_euros:
            return False
        
        # If grace period is disabled, block immediately
        if not self.enable_grace_period:
            return True
        
        # Check if grace period has expired
        current_time = int(time.time())
        grace_period_seconds = self.grace_period_hours * 3600
        
        if current_time - last_topup_timestamp > grace_period_seconds:
            return True
        
        return False
    
    def get_balance_status(self, balance_euros: float) -> str:
        """
        Get human-readable balance status.
        
        Args:
            balance_euros: Current wallet balance
            
        Returns:
            Status string: 'healthy', 'low', 'critical'
        """
        if balance_euros >= self.low_balance_threshold_euros:
            return "healthy"
        elif balance_euros >= self.critical_balance_threshold_euros:
            return "low"
        else:
            return "critical"


# ============= GLOBAL INSTANCE =============
# This is the single source of truth for all billing rules
BILLING_RULES = BillingRules()


# ============= HELPER FUNCTIONS =============

def get_pricing_display() -> List[dict]:
    """
    Get pricing tiers in a format suitable for frontend display.
    
    Returns:
        List of pricing tier dictionaries
    """
    return [
        {
            "duration_min": tier.min_duration_seconds // 60,
            "duration_max": tier.max_duration_seconds // 60 if tier.max_duration_seconds < 99999 else None,
            "price": tier.price_euros,
            "label": tier.display_name
        }
        for tier in BILLING_RULES.pricing_tiers
    ]


def calculate_monthly_cost_estimate(avg_calls_per_day: int, avg_duration_seconds: int) -> float:
    """
    Estimate monthly cost based on usage patterns.
    
    Args:
        avg_calls_per_day: Average number of calls per day
        avg_duration_seconds: Average call duration in seconds
        
    Returns:
        Estimated monthly cost in euros
    """
    cost_per_call = BILLING_RULES.calculate_call_cost(avg_duration_seconds)
    monthly_calls = avg_calls_per_day * 30
    return cost_per_call * monthly_calls


if __name__ == "__main__":
    # Test the billing rules
    print("=== DaVinci AI Billing Rules ===")
    print(f"\nPricing Tiers:")
    for tier in BILLING_RULES.pricing_tiers:
        print(f"  {tier.display_name}: €{tier.price_euros}")
    
    print(f"\n Wallet Configuration:")
    print(f"  Minimum Balance: €{BILLING_RULES.minimum_balance_euros}")
    print(f"  Low Balance Threshold: €{BILLING_RULES.low_balance_threshold_euros}")
    
    print(f"\nExample Calculations:")
    print(f"  3 min call: €{BILLING_RULES.calculate_call_cost(180)}")
    print(f"  7 min call: €{BILLING_RULES.calculate_call_cost(420)}")
    print(f"  12 min call: €{BILLING_RULES.calculate_call_cost(720)}")
    print(f"  20 min call: €{BILLING_RULES.calculate_call_cost(1200)}")
    
    print(f"\nEstimated Calls with €50 balance: {BILLING_RULES.get_estimated_calls_remaining(50.0)}")

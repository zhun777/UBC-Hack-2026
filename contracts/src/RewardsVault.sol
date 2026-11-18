// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {PointsToken} from "./PointsToken.sol";

/// @title RewardsVault
/// @notice Holds the USDC behind every reward point.
///         - Each brand pre-funds a USDC reward budget.
///         - The network (owner) issues points to a customer from a brand's budget.
///         - A customer spends points at any active brand; the USDC behind them is
///           paid straight to that brand's settlement address.
///         Invariant: USDC held = sum of brand budgets + points outstanding x POINT_VALUE.
contract RewardsVault is Ownable {
    using SafeERC20 for IERC20;

    /// @notice USDC units (6 decimals) behind one point: $0.01.
    uint256 public constant POINT_VALUE = 10_000;

    struct Brand {
        address settlement; // where this brand's operator gets paid
        string currency; // ISO code of the operator's local currency, e.g. "SGD"
        bool active;
        bool exists;
        uint256 budget; // USDC units available to fund new rewards
    }

    IERC20 public immutable usdc;
    PointsToken public immutable points;

    mapping(bytes32 brandId => Brand) private _brands;
    mapping(bytes32 orderId => bool) public orderPaid;
    bytes32[] public brandIds;

    error BrandExists();
    error UnknownBrand();
    error BrandInactive();
    error ZeroAddress();
    error ZeroAmount();
    error InvalidOrder();
    error OrderAlreadyPaid();
    error InsufficientBudget(uint256 needed, uint256 available);
    error InsufficientPoints(uint256 needed, uint256 available);

    event BrandAdded(bytes32 indexed brandId, address settlement, string currency);
    event BrandActiveSet(bytes32 indexed brandId, bool active);
    event BrandSettlementSet(bytes32 indexed brandId, address settlement);
    event BrandFunded(bytes32 indexed brandId, address indexed funder, uint256 usdcAmount);
    event RewardIssued(bytes32 indexed brandId, address indexed user, uint256 points, uint256 usdcAmount);
    event Spent(
        address indexed user,
        bytes32 indexed brandId,
        bytes32 branchId,
        bytes32 indexed orderId,
        uint256 points,
        uint256 usdcAmount
    );

    constructor(address initialOwner, IERC20 usdc_, PointsToken points_) Ownable(initialOwner) {
        if (address(usdc_) == address(0) || address(points_) == address(0)) revert ZeroAddress();
        usdc = usdc_;
        points = points_;
    }

    // ---------------------------------------------------------------- brands

    function addBrand(bytes32 brandId, address settlement, string calldata currency) external onlyOwner {
        if (_brands[brandId].exists) revert BrandExists();
        if (settlement == address(0)) revert ZeroAddress();
        _brands[brandId] = Brand({settlement: settlement, currency: currency, active: true, exists: true, budget: 0});
        brandIds.push(brandId);
        emit BrandAdded(brandId, settlement, currency);
    }

    function setBrandActive(bytes32 brandId, bool active) external onlyOwner {
        _requireExists(brandId);
        _brands[brandId].active = active;
        emit BrandActiveSet(brandId, active);
    }

    function setBrandSettlement(bytes32 brandId, address settlement) external onlyOwner {
        _requireExists(brandId);
        if (settlement == address(0)) revert ZeroAddress();
        _brands[brandId].settlement = settlement;
        emit BrandSettlementSet(brandId, settlement);
    }

    /// @notice Adds USDC to a brand's reward budget. Anyone can fund; the caller must
    ///         first approve the vault for `usdcAmount`.
    function fundBrand(bytes32 brandId, uint256 usdcAmount) external {
        _requireExists(brandId);
        if (usdcAmount == 0) revert ZeroAmount();
        _brands[brandId].budget += usdcAmount;
        usdc.safeTransferFrom(msg.sender, address(this), usdcAmount);
        emit BrandFunded(brandId, msg.sender, usdcAmount);
    }

    // --------------------------------------------------------------- rewards

    /// @notice Issues points to a customer, paid for out of the brand's budget.
    function issueReward(bytes32 brandId, address user, uint256 pointsAmount) external onlyOwner {
        Brand storage b = _requireActive(brandId);
        if (user == address(0)) revert ZeroAddress();
        if (pointsAmount == 0) revert ZeroAmount();
        uint256 cost = pointsAmount * POINT_VALUE;
        if (b.budget < cost) revert InsufficientBudget(cost, b.budget);
        b.budget -= cost;
        points.mint(user, pointsAmount);
        emit RewardIssued(brandId, user, pointsAmount, cost);
    }

    /// @notice Spends the caller's points at a brand. Burns the points and pays the
    ///         USDC behind them to the brand's settlement address. Each order ID can
    ///         be paid once.
    function spendAtBrand(bytes32 brandId, bytes32 branchId, bytes32 orderId, uint256 pointsAmount) external {
        Brand storage b = _requireActive(brandId);
        if (pointsAmount == 0) revert ZeroAmount();
        if (orderId == bytes32(0)) revert InvalidOrder();
        if (orderPaid[orderId]) revert OrderAlreadyPaid();
        uint256 balance = points.balanceOf(msg.sender);
        if (balance < pointsAmount) revert InsufficientPoints(pointsAmount, balance);

        orderPaid[orderId] = true;
        uint256 payout = pointsAmount * POINT_VALUE;
        points.burn(msg.sender, pointsAmount);
        usdc.safeTransfer(b.settlement, payout);
        emit Spent(msg.sender, brandId, branchId, orderId, pointsAmount, payout);
    }

    // ----------------------------------------------------------------- views

    function getBrand(bytes32 brandId) external view returns (Brand memory) {
        return _brands[brandId];
    }

    function brandCount() external view returns (uint256) {
        return brandIds.length;
    }

    /// @notice USDC that must be held: all budgets plus every outstanding point.
    function totalLiabilities() public view returns (uint256 total) {
        for (uint256 i = 0; i < brandIds.length; i++) {
            total += _brands[brandIds[i]].budget;
        }
        total += points.totalSupply() * POINT_VALUE;
    }

    /// @notice True when the USDC in the vault covers every budget and every point.
    function isFullyBacked() external view returns (bool) {
        return usdc.balanceOf(address(this)) >= totalLiabilities();
    }

    // -------------------------------------------------------------- internal

    function _requireExists(bytes32 brandId) private view returns (Brand storage b) {
        b = _brands[brandId];
        if (!b.exists) revert UnknownBrand();
    }

    function _requireActive(bytes32 brandId) private view returns (Brand storage b) {
        b = _requireExists(brandId);
        if (!b.active) revert BrandInactive();
    }
}

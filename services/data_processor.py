"""
Data preprocessing and management module
Converts Colab data processing logic into reusable service
"""

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


class DataProcessor:
    """Handle data loading, preprocessing, and storage"""
    
    def __init__(self):
        self.df_original = None
        self.df_processed = None
        
    def _normalize_columns(self, df):
        """Map common variations of column names to standard names"""
        mapping = {
            'clientName': ['client name', 'client_name', 'customer name', 'client', 'customer'],
            'groupName': ['group name', 'group_name', 'group'],
            'loName': ['lo name', 'lo_name', 'loan officer', 'loname'],
            'loanAmount': ['loan amount', 'loan_amount', 'loanamount', 'principal', 'amount'],
            'totalPayment': ['total payment', 'total_payment', 'totalpayment', 'paid amount', 'amount paid'],
            'OverdueCollectionCount': ['overdue count', 'overdue_count', 'overdue', 'overduecollectioncount', 'unpaid count'],
            'cycle': ['cycle', 'loan cycle', 'loan_cycle'],
            'loanPurpose': ['loan purpose', 'loan_purpose', 'business', 'business type', 'sector'],
            'disbursementDate': ['disbursement date', 'disbursement_date', 'date', 'loan date']
        }
        
        new_cols = {}
        for col in df.columns:
            col_orig = str(col)
            col_clean = col_orig.lower().strip()
            found = False
            for std_name, variations in mapping.items():
                if col_clean == std_name.lower() or col_clean in variations:
                    new_cols[col_orig] = std_name
                    found = True
                    break
            if not found:
                new_cols[col_orig] = col_orig
                
        return df.rename(columns=new_cols)

    def load_data(self, file_path):
        """Load CSV or Excel file into memory and convert Excel to CSV"""
        try:
            is_excel = False
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith('.xlsx') or file_path.endswith('.xls'):
                df = pd.read_excel(file_path)
                is_excel = True
            else:
                return False, "Unsupported file format. Please upload CSV or Excel."
            
            # Normalize column names
            self.df_original = self._normalize_columns(df)
            
            # Convert Excel to CSV if requested
            if is_excel:
                csv_path = file_path.rsplit('.', 1)[0] + '.csv'
                self.df_original.to_csv(csv_path, index=False)
                
            self.df_processed = self.preprocess_data(self.df_original)
            return True, f"Data loaded: {self.df_processed.shape[0]} rows, {self.df_processed.shape[1]} columns"
        except Exception as e:
            return False, f"Error loading data: {str(e)}"
    
    def preprocess_data(self, df):
        """Clean and preprocess the data"""
        data = df.copy()
        
        # Ensure critical columns exist with defaults
        required_columns = {
            'clientName': 'Unknown Client',
            'groupName': 'No Group',
            'loName': 'Unknown LO',
            'loanAmount': 0,
            'totalPayment': 0,
            'OverdueCollectionCount': 0,
            'cycle': 1,
            'loanPurpose': 'General',
            'disbursementDate': pd.Timestamp.now()
        }
        
        for col, default_val in required_columns.items():
            if col not in data.columns:
                data[col] = default_val
        
        # Replace all NaN/None with defaults or valid JSON types
        data = data.replace({np.nan: None})
        
        # Numeric columns fill NA
        numeric_columns = ['loanAmount', 'totalPayment', 'OverdueCollectionCount', 'cycle']
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
        
        # String columns fill NA
        string_columns = ['clientName', 'groupName', 'loName', 'loanPurpose']
        for col in string_columns:
            if col in data.columns:
                data[col] = data[col].fillna('N/A').astype(str)
        
        # Date processing
        if 'disbursementDate' in data.columns:
            data['disbursementDate'] = pd.to_datetime(data['disbursementDate'], errors='coerce')
        
        # Calculate scores and levels
        data['repayment_rate'] = data.apply(
            lambda row: (row['totalPayment'] / row['loanAmount'] * 100) if row['loanAmount'] > 0 else 0,
            axis=1
        )
        
        data['is_overdue'] = data['OverdueCollectionCount'] > 0
        data['client_performance_score'] = data.apply(self._calculate_client_score, axis=1)
        
        # FINAL CLEAN: Ensure NO NaN values remain before returning
        return data.where(pd.notnull(data), None)
    
    def _calculate_client_score(self, row):
        """
        Calculate client performance score (0-100)
        Higher score = better performance
        """
        score = 100
        
        # Penalty for overdue collections
        overdue = row.get('OverdueCollectionCount', 0)
        try:
            overdue = int(overdue) if pd.notna(overdue) else 0
        except (ValueError, TypeError):
            overdue = 0
        score -= overdue * 10
        
        # Reward for good repayment rate
        repayment_rate = row.get('repayment_rate', 0)
        try:
            repayment_rate = float(repayment_rate) if pd.notna(repayment_rate) else 0
        except (ValueError, TypeError):
            repayment_rate = 0
            
        if repayment_rate >= 1:
            score += 20
        elif repayment_rate >= 0.8:
            score += 10
        
        # Reward for loan cycles (repeat customers)
        cycle = row.get('cycle', 0)
        try:
            cycle = int(cycle) if pd.notna(cycle) else 0
        except (ValueError, TypeError):
            cycle = 0
        score += cycle * 5
        
        # Keep score in 0-100 range
        return max(0, min(100, score))
    
    def get_basic_stats(self):
        """Get basic statistics about the dataset"""
        if self.df_processed is None:
            return None
            
        stats = {
            'total_clients': int(self.df_processed['clientName'].nunique()) if 'clientName' in self.df_processed.columns else 0,
            'total_groups': int(self.df_processed['groupName'].nunique()) if 'groupName' in self.df_processed.columns else 0,
            'total_loan_officers': int(self.df_processed['loName'].nunique()) if 'loName' in self.df_processed.columns else 0,
            'average_loan_amount': float(self.df_processed['loanAmount'].mean()) if 'loanAmount' in self.df_processed.columns else 0,
            'average_client_score': float(self.df_processed['client_performance_score'].mean()),
            'total_loans': int(len(self.df_processed)),
            'total_loan_portfolio': float(self.df_processed['loanAmount'].sum()) if 'loanAmount' in self.df_processed.columns else 0,
            'clients_with_overdue': int(self.df_processed['is_overdue'].sum()),
        }
        
        return stats
    
    def get_all_clients(self, limit=100, offset=0, search=None):
        """Get list of clients with pagination and search"""
        if self.df_processed is None:
            return []
        
        # Get unique clients with their latest info
        clients_df = self.df_processed.sort_values('disbursementDate', ascending=False).drop_duplicates('clientName')
        
        # Apply search filter
        if search:
            clients_df = clients_df[clients_df['clientName'].str.contains(search, case=False, na=False)]
        
        # Apply pagination
        clients_df = clients_df.iloc[offset:offset+limit]
        
        # Convert to list of dicts
        clients = []
        for _, row in clients_df.iterrows():
            clients.append({
                'name': row['clientName'],
                'group': row.get('groupName', 'N/A'),
                'loan_officer': row.get('loName', 'N/A'),
                'performance_score': float(row['client_performance_score']),
                'loan_amount': float(row.get('loanAmount', 0)),
                'overdue_count': int(row.get('OverdueCollectionCount', 0))
            })
        
        return clients
    
    def get_all_groups(self, limit=100, offset=0, search=None):
        """Get list of groups with pagination and search"""
        if self.df_processed is None:
            return []
        
        # Group by group name
        groups_df = self.df_processed.groupby('groupName').agg({
            'client_performance_score': 'mean',
            'clientName': 'count',
            'OverdueCollectionCount': 'sum',
            'loanAmount': 'sum'
        }).reset_index()
        
        groups_df.columns = ['name', 'avg_score', 'member_count', 'total_overdue', 'total_loan_amount']
        
        # Apply search filter
        if search:
            groups_df = groups_df[groups_df['name'].str.contains(search, case=False, na=False)]
        
        # Apply pagination
        groups_df = groups_df.iloc[offset:offset+limit]
        
        # Convert to list of dicts
        groups = []
        for _, row in groups_df.iterrows():
            groups.append({
                'name': row['name'],
                'avg_score': float(row['avg_score']),
                'member_count': int(row['member_count']),
                'total_overdue': int(row['total_overdue']),
                'total_loan_amount': float(row['total_loan_amount'])
            })
        
        return groups
    
    def find_client(self, client_name):
        """Find client by name (partial match)"""
        if self.df_processed is None:
            return None
        
        # Find matching clients
        matches = self.df_processed[
            self.df_processed['clientName'].str.contains(client_name, case=False, na=False)
        ]
        
        if matches.empty:
            return None
        
        # Return the most recent record for this client
        client_data = matches.sort_values('disbursementDate', ascending=False).iloc[0]
        
        return client_data.to_dict()
    
    def find_group(self, group_name):
        """Find group by name (partial match)"""
        if self.df_processed is None:
            return None
        
        # Find matching groups
        matches = self.df_processed[
            self.df_processed['groupName'].str.contains(group_name, case=False, na=False)
        ]
        
        if matches.empty:
            return None
        
        # Get group statistics
        group_data = matches.groupby('groupName').agg({
            'client_performance_score': ['mean', 'count'],
            'OverdueCollectionCount': 'sum',
            'loanAmount': ['sum', 'mean'],
            'repayment_rate': 'mean'
        }).iloc[0]
        
        result = {
            'groupName': matches.iloc[0]['groupName'],
            'avg_score': float(group_data[('client_performance_score', 'mean')]),
            'member_count': int(group_data[('client_performance_score', 'count')]),
            'total_overdue': int(group_data[('OverdueCollectionCount', 'sum')]),
            'total_loan_amount': float(group_data[('loanAmount', 'sum')]),
            'avg_loan_amount': float(group_data[('loanAmount', 'mean')]),
            'avg_repayment_rate': float(group_data[('repayment_rate', 'mean')]),
        }
        
        return result
    
    def get_group_members(self, group_name, top_n=5):
        """Get top performing members of a group"""
        if self.df_processed is None:
            return []
        
        # Get all members of the group
        members = self.df_processed[
            self.df_processed['groupName'].str.contains(group_name, case=False, na=False)
        ]
        
        if members.empty:
            return []
        
        # Get top performers
        top_members = members.nlargest(top_n, 'client_performance_score')
        
        result = []
        for _, member in top_members.iterrows():
            result.append({
                'name': member['clientName'],
                'score': float(member['client_performance_score']),
                'loan_amount': float(member.get('loanAmount', 0)),
                'overdue_count': int(member.get('OverdueCollectionCount', 0))
            })
        
        return result


# Global instance
data_processor = DataProcessor()
